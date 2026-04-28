"""Permanent-gap awareness for vnmarket SDK."""

import json
from datetime import date

from google.cloud import storage


def load_gaps(project_id: str, env: str, stream: str) -> list[dict]:
    """Load permanent gaps for a stream.

    Returns list of dicts with at least {start: date, end: date, reason: str}.
    Returns empty list if file absent or unreadable.
    """
    bucket_name = f"vn-market-lake-{env}"
    blob_name = f"_ops/permanent-gaps/{stream}.jsonl"
    try:
        client = storage.Client(project=project_id)
        blob = client.bucket(bucket_name).blob(blob_name)
        if not blob.exists():
            return []
        text = blob.download_as_text()
    except Exception:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "start" in rec and isinstance(rec["start"], str):
            try:
                rec["start"] = date.fromisoformat(rec["start"])
            except ValueError:
                pass
        if "end" in rec and isinstance(rec["end"], str):
            try:
                rec["end"] = date.fromisoformat(rec["end"])
            except ValueError:
                pass
        out.append(rec)
    return out
