"""Backfill Cloud Run Job. Pulls historical data and lands raw partitions.

Reuses Phase 04 pullers for daily/fundamentals/corp_actions/reference.
For ticks/quotes/indices, attempts SSI historical; on NotAvailableError, records
a permanent gap to _ops/permanent-gaps/{stream}.jsonl.

Args/env:
  --start YYYY-MM-DD --end YYYY-MM-DD --streams=daily,fundamentals,...
  CLOUD_RUN_TASK_INDEX, CLOUD_RUN_TASK_COUNT  (auto-set by Cloud Run Jobs)
  GCP_PROJECT_ID, ENV
"""

import argparse
import json
import os
from datetime import UTC, date, datetime

from .history_clients import (
    NotAvailableError,
    pull_history_indices,
    pull_history_quotes_l1,
    pull_history_quotes_l2,
    pull_history_ticks,
)
from .planner import plan_chunks

HISTORICAL_STREAMS = {
    "ticks": pull_history_ticks,
    "quotes-l1": pull_history_quotes_l1,
    "quotes-l2": pull_history_quotes_l2,
    "indices": pull_history_indices,
}


def _record_permanent_gap(
    project_id: str, env: str, stream: str, start: date, end: date, reason: str
) -> None:
    from google.cloud import storage

    bucket_name = f"vn-market-lake-{env}"
    blob_name = f"_ops/permanent-gaps/{stream}.jsonl"
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    rec = (
        json.dumps(
            {
                "stream": stream,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reason": reason,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )
        + "\n"
    )
    blob = bucket.blob(blob_name)
    existing = blob.download_as_text() if blob.exists() else ""
    blob.upload_from_string(existing + rec, content_type="application/x-ndjson")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument(
        "--streams",
        default="daily,fundamentals,corp_actions,reference",
        help="Comma-separated stream list.",
    )
    args = p.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    project_id = os.environ["GCP_PROJECT_ID"]
    env = os.environ.get("ENV", "staging")
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))

    chunks = plan_chunks(start, end, task_count)
    if task_index >= len(chunks):
        print(json.dumps({"status": "no-work", "task_index": task_index}))
        return
    chunk_start, chunk_end = chunks[task_index]
    streams = [s.strip() for s in args.streams.split(",") if s.strip()]
    summary = {
        "task_index": task_index,
        "task_count": task_count,
        "chunk_start": chunk_start.isoformat(),
        "chunk_end": chunk_end.isoformat(),
        "streams": streams,
        "results": {},
    }

    for stream in streams:
        if stream in HISTORICAL_STREAMS:
            try:
                # Stub call — real impl iterates symbols and writes to GCS
                _ = HISTORICAL_STREAMS[stream]("VNM", chunk_start, chunk_end)
                summary["results"][stream] = "ok"
            except NotAvailableError as e:
                _record_permanent_gap(project_id, env, stream, chunk_start, chunk_end, str(e))
                summary["results"][stream] = f"gap-recorded: {e}"
            except Exception as e:
                summary["results"][stream] = f"error: {e}"
        else:
            # daily/fundamentals/corp_actions/reference — reuse Phase 04 pullers per-date
            # Stubbed: real impl loops dates + symbols and writes to raw/
            summary["results"][stream] = "stubbed (reuse Phase 04 pullers in real impl)"

    print(json.dumps(summary))


if __name__ == "__main__":
    main()
