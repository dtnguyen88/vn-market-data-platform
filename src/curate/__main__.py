"""Curate entrypoint. Cloud Run Job dispatching by --stream arg.

Reads raw/{stream}/.../{date}/, applies stream-specific dedup + derive,
writes curated/{stream}/.../{date}/. Idempotent overwrite per partition.

Args (or env-var fallbacks):
  --stream {ticks|quotes-l1|quotes-l2|indices|daily-ohlcv|fundamentals|corp-actions}
  --date YYYY-MM-DD                       (default: yesterday in Asia/Ho_Chi_Minh)

Env:
  ENV                staging|prod|test
  GCP_PROJECT_ID     informational
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from .streams.corp_actions import curate_corp_actions
from .streams.daily_ohlcv import curate_daily_ohlcv
from .streams.fundamentals import curate_fundamentals
from .streams.indices import curate_indices
from .streams.quotes_l1 import curate_quotes_l1
from .streams.quotes_l2 import curate_quotes_l2
from .streams.ticks import curate_ticks

DEFAULT_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
log = structlog.get_logger(__name__)

VALID_STREAMS = {
    "ticks",
    "quotes-l1",
    "quotes-l2",
    "indices",
    "daily-ohlcv",
    "fundamentals",
    "corp-actions",
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Curate raw -> curated for one stream.")
    p.add_argument(
        "--stream",
        default=os.environ.get("STREAM"),
        help="Stream name; required (or set STREAM env var).",
    )
    p.add_argument(
        "--date",
        default=os.environ.get("TARGET_DATE"),
        help="Target date YYYY-MM-DD; default yesterday VN time.",
    )
    args = p.parse_args()
    if not args.stream:
        p.error("--stream (or STREAM env) required")
    if args.stream not in VALID_STREAMS:
        p.error(f"--stream must be one of {sorted(VALID_STREAMS)}")
    if args.date:
        args.date_obj = date.fromisoformat(args.date)
    else:
        args.date_obj = (datetime.now(DEFAULT_TZ) - timedelta(days=1)).date()
    return args


def _build_uris(stream: str, target_date: date, env: str) -> tuple[str, str]:
    """Build raw and curated GCS URIs for a given stream, date, and environment."""
    bucket = f"vn-market-lake-{env}"
    d = target_date.isoformat()
    y = target_date.year
    if stream == "ticks":
        raw = f"gs://{bucket}/raw/ticks/date={d}/**/*.parquet"
        curated = f"gs://{bucket}/curated/ticks/date={d}/_curate_run.parquet"
    elif stream == "quotes-l1":
        raw = f"gs://{bucket}/raw/quotes-l1/date={d}/**/*.parquet"
        curated = f"gs://{bucket}/curated/quotes-l1/date={d}/_curate_run.parquet"
    elif stream == "quotes-l2":
        raw = f"gs://{bucket}/raw/quotes-l2/date={d}/**/*.parquet"
        curated = f"gs://{bucket}/curated/quotes-l2/date={d}/_curate_run.parquet"
    elif stream == "indices":
        raw = f"gs://{bucket}/raw/indices/date={d}/**/*.parquet"
        curated = f"gs://{bucket}/curated/indices/date={d}/_curate_run.parquet"
    elif stream == "daily-ohlcv":
        raw = f"gs://{bucket}/raw/daily-ohlcv/year={y}/date={d}/**/*.parquet"
        curated = f"gs://{bucket}/curated/daily-ohlcv/year={y}/_curate_run.parquet"
    elif stream == "fundamentals":
        raw = f"gs://{bucket}/raw/fundamentals/**/*.parquet"
        curated = f"gs://{bucket}/curated/fundamentals/_curate_run.parquet"
    elif stream == "corp-actions":
        raw = f"gs://{bucket}/raw/corp-actions/year={y}/**/*.parquet"
        curated = f"gs://{bucket}/curated/corp-actions/year={y}/_curate_run.parquet"
    else:
        raise ValueError(f"unknown stream: {stream}")
    return raw, curated


def main() -> int:
    """Parse args, build URIs, dispatch to stream curate function, emit JSON summary."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    env = os.environ["ENV"]
    target_date: date = args.date_obj
    stream: str = args.stream
    raw_uri, curated_uri = _build_uris(stream, target_date, env)
    log.info(
        "curate start",
        stream=stream,
        date=target_date.isoformat(),
        raw=raw_uri,
        curated=curated_uri,
    )
    try:
        if stream == "ticks":
            metrics = curate_ticks(raw_uri, curated_uri)
        elif stream == "quotes-l1":
            metrics = curate_quotes_l1(raw_uri, curated_uri)
        elif stream == "quotes-l2":
            metrics = curate_quotes_l2(raw_uri, curated_uri)
        elif stream == "indices":
            metrics = curate_indices(raw_uri, curated_uri)
        elif stream == "daily-ohlcv":
            ca_uri = f"gs://vn-market-lake-{env}/raw/corp-actions/**/*.parquet"
            metrics = curate_daily_ohlcv(raw_uri, ca_uri, curated_uri)
        elif stream == "fundamentals":
            metrics = curate_fundamentals(raw_uri, curated_uri)
        elif stream == "corp-actions":
            metrics = curate_corp_actions(raw_uri, curated_uri)
        else:
            raise ValueError(f"unhandled stream: {stream}")
    except Exception as e:
        log.exception("curate failed", stream=stream)
        summary = {
            "stream": stream,
            "date": target_date.isoformat(),
            "env": env,
            "status": "error",
            "error": str(e),
            "ts": datetime.now(UTC).isoformat(),
        }
        print(json.dumps(summary))
        return 1

    summary = {
        "stream": stream,
        "date": target_date.isoformat(),
        "env": env,
        "status": "ok",
        **metrics,
        "ts": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
