"""Reference snapshot job — pulls tickers + futures, writes Parquet, emits summary.

Cloud Run Job entrypoint. Daily; idempotent re-run overwrites snapshot for the date.

Env:
  ENV         staging|prod|test
  TARGET_DATE optional override (YYYY-MM-DD); default yesterday in Asia/Ho_Chi_Minh
"""

import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import structlog
from google.cloud import storage

from .futures import pull_futures
from .tickers import pull_tickers

log = structlog.get_logger(__name__)
DEFAULT_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _resolve_target_date() -> date:
    """Return target date from env var or yesterday in Vietnam time."""
    raw = os.environ.get("TARGET_DATE")
    if raw:
        return date.fromisoformat(raw)
    return (datetime.now(DEFAULT_TZ) - timedelta(days=1)).date()


def _upload_parquet(bucket: storage.Bucket, key: str, df: pl.DataFrame) -> None:
    """Serialize DataFrame to Parquet and upload to GCS. Overwrites existing blob."""
    buf = BytesIO()
    df.write_parquet(buf, compression="zstd", compression_level=3, statistics=True)
    bucket.blob(key).upload_from_string(buf.getvalue(), content_type="application/octet-stream")


def main() -> None:
    """Entrypoint — pull tickers + futures, write Parquet snapshots, emit JSON summary."""
    logging.basicConfig(level=logging.INFO)
    env = os.environ["ENV"]
    target_date = _resolve_target_date()
    bucket_name = f"vn-market-lake-{env}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    summary: dict = {
        "date": target_date.isoformat(),
        "env": env,
        "tickers_rows": 0,
        "futures_rows": 0,
        "errors": [],
        "ts": datetime.now(UTC).isoformat(),
    }
    log.info("reference start", date=target_date.isoformat(), env=env)

    try:
        df = pull_tickers()
        if df.height > 0:
            key = f"raw/reference/tickers/snapshot={target_date.isoformat()}/part-0.parquet"
            _upload_parquet(bucket, key, df)
            summary["tickers_rows"] = df.height
    except Exception as e:
        log.warning("tickers failed", error=str(e))
        summary["errors"].append({"stream": "tickers", "error": str(e)})

    try:
        df = pull_futures()
        if df.height > 0:
            key = (
                f"raw/reference/futures_contracts/snapshot={target_date.isoformat()}/part-0.parquet"
            )
            _upload_parquet(bucket, key, df)
            summary["futures_rows"] = df.height
    except Exception as e:
        log.warning("futures failed", error=str(e))
        summary["errors"].append({"stream": "futures", "error": str(e)})

    # Single JSON-line to stdout — orchestration layer ingests this for monitoring
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
