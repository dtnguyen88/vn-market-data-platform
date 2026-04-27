"""Per-flush ingest receipt writer for audit + gap detection."""

import json
import time
from datetime import date

from .gcs_uploader import GcsUploader


def write_receipt(uploader: GcsUploader, stream: str, receipt: dict) -> None:
    """Write a single JSONL receipt line to GCS under _ops/ingest-receipts/."""
    d: date = receipt["date"]
    payload = {**receipt, "date": d.isoformat()}
    line = json.dumps(payload) + "\n"
    name = f"_ops/ingest-receipts/{d.isoformat()}/{stream}/{int(time.time() * 1000)}.jsonl"
    uploader.upload(name, line.encode("utf-8"), content_type="application/x-ndjson")
