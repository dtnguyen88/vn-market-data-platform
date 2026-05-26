"""Realtime publisher entrypoint. Runs as Cloud Run service with min=max=1 per shard.

Streams SSI FastConnect v3 → parses → publishes to Pub/Sub topics. Tiny ASGI
app sits alongside so Cloud Run's startup probe passes; the streaming loop
runs as a background task. If it dies (bad creds, WS error, market closed),
the HTTP server keeps the container up so the heartbeat metric stays
observable and alerts can fire.

One wire frame can fan out to multiple Pub/Sub topics — e.g. each `quote.<sym>`
event produces both a QuoteL1 (best bid/ask + derived mid/spread) and a
QuoteL2 (full 10-level book).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import uvicorn
from google.cloud import secretmanager, storage

from .config import Config
from .heartbeat import Heartbeat
from .parsers import (
    parse_foreign_room,
    parse_odd_lot,
    parse_put_through,
    parse_quote_l1,
    parse_quote_l2,
    parse_tick,
)
from .pubsub_publisher import PubsubPublisher
from .ssi_v3_adapter import V3StreamAdapter

log = logging.getLogger(__name__)

# Pub/Sub topic names — match infra/modules/pubsub-topic outputs
T_TICKS = "market-ticks"
T_QUOTES_L1 = "market-quotes-l1"
T_QUOTES_L2 = "market-quotes-l2"
T_FOREIGN_ROOM = "market-foreign-room"  # may not yet exist in IaC; soft-drop on NotFound
T_PUT_THROUGH = "market-put-through"
T_ODD_LOT = "market-odd-lot"


def _resolve_secret(project: str, name: str) -> str:
    sm = secretmanager.SecretManagerServiceClient()
    full = f"projects/{project}/secrets/{name}/versions/latest"
    return sm.access_secret_version(name=full).payload.data.decode()


def _load_symbols(symbols_url: str) -> tuple[list[str], list[str]]:
    """Load shard manifest from GCS. Returns (symbols, indices)."""
    storage_client = storage.Client()
    bucket_name, *blob_parts = symbols_url.replace("gs://", "").split("/")
    blob = storage_client.bucket(bucket_name).blob("/".join(blob_parts))
    payload = json.loads(blob.download_as_text())
    if isinstance(payload, list):
        return payload, []  # legacy format: bare list of symbols
    return payload.get("symbols", []), payload.get("indices", [])


async def _stream_loop(cfg: Config) -> None:
    api_key = _resolve_secret(cfg.project_id, cfg.ssi_api_key_secret)
    api_secret = _resolve_secret(cfg.project_id, cfg.ssi_api_secret_secret)
    private_key = _resolve_secret(cfg.project_id, cfg.ssi_private_key_secret)

    symbols, indices = _load_symbols(cfg.symbols_url)
    log.info("shard %d: %d symbols, %d indices", cfg.shard, len(symbols), len(indices))

    pubs = {
        t: PubsubPublisher(cfg.project_id, t)
        for t in (T_TICKS, T_QUOTES_L1, T_QUOTES_L2, T_FOREIGN_ROOM, T_PUT_THROUGH, T_ODD_LOT)
    }

    hb = Heartbeat(cfg.project_id, cfg.shard)
    _hb_task = asyncio.create_task(hb.run())  # noqa: RUF006  keep ref

    storage_client = storage.Client()
    dropped_per_topic: dict[str, int] = {}

    def _publish(topic: str, model, attrs: dict[str, str]) -> None:
        try:
            pubs[topic].publish(model, attrs)
        except Exception as e:
            dropped_per_topic[topic] = dropped_per_topic.get(topic, 0) + 1
            if dropped_per_topic[topic] in (1, 100, 1000):  # logarithmic alert
                log.warning(
                    "publish to %s failing (count=%d): %s",
                    topic,
                    dropped_per_topic[topic],
                    e,
                )

    async with V3StreamAdapter(
        api_key=api_key,
        api_secret=api_secret,
        private_key=private_key,
        symbols=symbols,
        indices=indices,
    ) as stream:
        async for topic, data, ts in stream.frames():
            try:
                await _dispatch(topic, data, ts, _publish, storage_client, cfg)
            except Exception as e:
                log.warning("parse error on %s: %s", topic, e)
                await asyncio.to_thread(
                    _record_parse_error, storage_client, cfg, topic, data, ts, e
                )


async def _dispatch(topic, data, ts, publish_fn, storage_client, cfg) -> None:
    """Route a raw wire frame to the right parser(s) + Pub/Sub topic(s)."""
    if topic.startswith("trade."):
        model = parse_tick(data, ts)
        publish_fn(T_TICKS, model, _attrs(model, "1", cfg.shard))
    elif topic.startswith("quote."):
        l1 = parse_quote_l1(data, ts)
        l2 = parse_quote_l2(data, ts)
        publish_fn(T_QUOTES_L1, l1, _attrs(l1, "1", cfg.shard))
        publish_fn(T_QUOTES_L2, l2, _attrs(l2, "1", cfg.shard))
    elif topic.startswith("room."):
        model = parse_foreign_room(data, ts)
        publish_fn(T_FOREIGN_ROOM, model, _attrs(model, "1", cfg.shard))
    elif topic.startswith("put."):
        model = parse_put_through(data, ts)
        publish_fn(T_PUT_THROUGH, model, _attrs(model, "1", cfg.shard))
    elif topic.startswith("oddlot."):
        model = parse_odd_lot(data, ts)
        publish_fn(T_ODD_LOT, model, _attrs(model, "1", cfg.shard))
    # market.* never fires; index values come from REST polling, not stream


def _attrs(model, schema_version: str, shard: int) -> dict[str, str]:
    return {
        "symbol": getattr(model, "symbol", ""),
        "asset_class": model.asset_class.value if hasattr(model, "asset_class") else "",
        "schema_version": schema_version,
        "shard": str(shard),
    }


def _record_parse_error(storage_client, cfg, topic, data, ts, err) -> None:
    """F3.7: dump raw payload to _ops/parse-errors/{topic}/date=YYYY-MM-DD/{ms}.jsonl"""
    try:
        d = ts.date().isoformat()
        ms = int(ts.timestamp() * 1000)
        blob_name = f"_ops/parse-errors/{topic}/date={d}/{ms}.jsonl"
        storage_client.bucket(f"vn-market-lake-{cfg.env}").blob(blob_name).upload_from_string(
            json.dumps({"topic": topic, "raw": data, "ts": ts.isoformat(), "error": str(err)})
            + "\n",
            content_type="application/x-ndjson",
        )
    except Exception:
        log.exception("failed to record parse error")


def _make_asgi_app(stream_task_ref: dict, shard: int):
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        path = scope["path"]
        if path not in ("/", "/healthz"):
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"not found"})
            return
        task = stream_task_ref.get("task")
        body = {"status": "ok", "shard": shard}
        if task is not None and task.done() and task.exception():
            body = {"status": "degraded", "shard": shard, "stream_error": str(task.exception())}
        payload = json.dumps(body).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    return app


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config.from_env()

    stream_task_ref: dict = {}
    stream_task_ref["task"] = asyncio.create_task(_stream_loop(cfg))

    port = int(os.environ.get("PORT", "8080"))
    server = uvicorn.Server(
        uvicorn.Config(
            _make_asgi_app(stream_task_ref, cfg.shard),
            host="0.0.0.0",  # noqa: S104  Cloud Run requires 0.0.0.0
            port=port,
            log_level="warning",
        )
    )
    log.info("publisher shard %d listening on :%d", cfg.shard, port)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
