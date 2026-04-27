"""Parquet writer entrypoint. One Cloud Run service per stream.

Env: GCP_PROJECT_ID, ENV, STREAM (ticks|quotes-l1|quotes-l2|indices), SHARD (default 0).
Receives Pub/Sub push payloads at POST /, buffers, flushes Parquet to GCS every 5s.
"""

import asyncio
import base64
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from shared.schemas import IndexValue, QuoteL1, QuoteL2, Tick

from .buffer import RingBuffer
from .gcs_uploader import GcsUploader
from .parquet_writer import models_to_parquet
from .receipts import write_receipt
from .schema_validator import validate

STREAM = os.environ["STREAM"]
ENV = os.environ["ENV"]
SHARD = os.environ.get("SHARD", "0")
BUCKET = f"vn-market-lake-{ENV}"

MODEL_BY_STREAM = {
    "ticks": Tick,
    "quotes-l1": QuoteL1,
    "quotes-l2": QuoteL2,
    "indices": IndexValue,
}

PARTITION_FN = {
    "ticks": lambda m: (
        f"raw/ticks/date={m.ts_event.date()}/asset_class={m.asset_class.value}/symbol={m.symbol}"
    ),
    "quotes-l1": lambda m: (
        f"raw/quotes-l1/date={m.ts_event.date()}/asset_class={m.asset_class.value}/symbol={m.symbol}"
    ),
    "quotes-l2": lambda m: (
        f"raw/quotes-l2/date={m.ts_event.date()}/asset_class={m.asset_class.value}"
        f"/hour={m.ts_event.hour:02d}/symbol={m.symbol}"
    ),
    "indices": lambda m: (f"raw/indices/date={m.ts_event.date()}/index={m.index_code}"),
}

uploader = GcsUploader(BUCKET)
buffer = RingBuffer(max_bytes=50 * 1024 * 1024, max_age_s=60.0)
log = logging.getLogger(__name__)


async def flush_loop() -> None:
    """Background task: drain ready partitions every 5 seconds and write Parquet to GCS."""
    model_cls = MODEL_BY_STREAM[STREAM]
    while True:
        await asyncio.sleep(5)
        ready = buffer.drain_if_ready(now=time.time())
        for partition, items in ready.items():
            models = [model_cls.model_validate_json(it) for it in items]
            data = models_to_parquet(models)
            ts_ms = int(time.time() * 1000)
            key = f"{partition}/part-{SHARD}-{ts_ms}.parquet"
            url = uploader.upload(key, data)
            log.info("flushed %d rows to %s", len(models), url)
            try:
                write_receipt(
                    uploader,
                    STREAM,
                    {
                        "file": url,
                        "rows": len(models),
                        "min_ts": min(m.ts_event for m in models).isoformat(),
                        "max_ts": max(m.ts_event for m in models).isoformat(),
                        "schema_version": 1,
                        "date": models[0].ts_event.date(),
                    },
                )
            except Exception:
                log.exception("receipt write failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start flush_loop on startup; cancel + final-drain on shutdown."""
    task = asyncio.create_task(flush_loop())
    try:
        yield
    finally:
        task.cancel()
        # Final drain — flush any remaining buffered items before container exits.
        for partition, items in buffer.drain_all().items():
            try:
                model_cls = MODEL_BY_STREAM[STREAM]
                models = [model_cls.model_validate_json(it) for it in items]
                data = models_to_parquet(models)
                ts_ms = int(time.time() * 1000)
                uploader.upload(f"{partition}/part-{SHARD}-{ts_ms}-final.parquet", data)
            except Exception:
                log.exception("final-flush failed for %s", partition)


app = FastAPI(lifespan=lifespan)


@app.post("/")
async def receive(req: Request):
    """Handle a Pub/Sub push envelope. Validate, buffer, or reject to GCS."""
    envelope = await req.json()
    msg = envelope.get("message", {})
    body = base64.b64decode(msg.get("data", ""))
    model_cls = MODEL_BY_STREAM[STREAM]
    parsed = validate(body, model_cls)
    if parsed is None:
        d = datetime.now(UTC).date()
        rejected_key = f"_ops/rejected/{STREAM}/date={d}/{int(time.time() * 1000)}.jsonl"
        uploader.upload(rejected_key, body, content_type="application/json")
        return {"status": "rejected"}
    partition = PARTITION_FN[STREAM](parsed)
    buffer.add(item=parsed.model_dump_json().encode("utf-8"), key=partition)
    return {"status": "ok"}
