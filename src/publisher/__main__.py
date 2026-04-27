"""Realtime publisher entrypoint. Run as Cloud Run service with min=max=1 per shard.

Args via env: GCP_PROJECT_ID, ENV, SHARD, SYMBOLS_URL.
"""

import asyncio
import json
import logging

from google.cloud import secretmanager, storage

from .config import Config
from .heartbeat import Heartbeat
from .parsers import parse_index, parse_quote_l1, parse_quote_l2, parse_tick
from .pubsub_publisher import PubsubPublisher
from .ws_client import SsiWsClient

CHANNEL_ROUTING = {
    "tick": ("market-ticks", parse_tick),
    "l1": ("market-quotes-l1", parse_quote_l1),
    "l2": ("market-quotes-l2", parse_quote_l2),
    "index": ("market-indices", parse_index),
}


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config.from_env()
    log = logging.getLogger(__name__)

    # 1. Resolve secrets
    sm = secretmanager.SecretManagerServiceClient()
    username = sm.access_secret_version(
        name=f"projects/{cfg.project_id}/secrets/{cfg.ssi_username_secret}/versions/latest"
    ).payload.data.decode()
    password = sm.access_secret_version(
        name=f"projects/{cfg.project_id}/secrets/{cfg.ssi_password_secret}/versions/latest"
    ).payload.data.decode()

    # 2. Load symbol list for this shard from GCS
    storage_client = storage.Client()
    bucket_name, *blob_parts = cfg.symbols_url.replace("gs://", "").split("/")
    blob = storage_client.bucket(bucket_name).blob("/".join(blob_parts))
    symbols = json.loads(blob.download_as_text())
    log.info("loaded %d symbols for shard %d", len(symbols), cfg.shard)

    # 3. Per-topic publishers (keep one client open)
    pubs = {topic: PubsubPublisher(cfg.project_id, topic) for topic, _ in CHANNEL_ROUTING.values()}

    # 4. Start heartbeat task (fire-and-forget; reference kept to prevent GC)
    hb = Heartbeat(cfg.project_id, cfg.shard)
    _hb_task = asyncio.create_task(hb.run())  # noqa: RUF006

    # 5. Stream from SSI, parse, publish
    client = SsiWsClient(username, password, symbols)
    async for channel, payload, ts in client.stream():
        if channel not in CHANNEL_ROUTING:
            continue
        topic, parser = CHANNEL_ROUTING[channel]
        try:
            msg = parser(payload, ts)
        except Exception as e:
            log.warning("parse error on %s: %s", channel, e)
            # F3.7: write raw payload to _ops/parse-errors/{stream}/date=YYYY-MM-DD/{ms}.jsonl
            try:
                d = ts.date().isoformat()
                ms = int(ts.timestamp() * 1000)
                blob_name = f"_ops/parse-errors/{channel}/date={d}/{ms}.jsonl"
                storage_client.bucket(f"vn-market-lake-{cfg.env}").blob(
                    blob_name
                ).upload_from_string(
                    json.dumps(
                        {
                            "channel": channel,
                            "raw": payload,
                            "ts": ts.isoformat(),
                            "error": str(e),
                        }
                    )
                    + "\n",
                    content_type="application/x-ndjson",
                )
            except Exception:
                log.exception("failed to record parse error")
            continue
        attrs = {
            "symbol": getattr(msg, "symbol", "") or getattr(msg, "index_code", ""),
            "asset_class": (msg.asset_class.value if hasattr(msg, "asset_class") else "index"),
            "schema_version": "1",
            "shard": str(cfg.shard),
        }
        pubs[topic].publish(msg, attrs)


if __name__ == "__main__":
    asyncio.run(main())
