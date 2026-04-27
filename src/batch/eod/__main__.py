"""EOD batch ingest job — daily OHLCV + fundamentals + corp actions.

Cloud Run Job entrypoint. One execution per trading day; idempotent re-run.

Env:
  GCP_PROJECT_ID    GCP project (informational; not yet used in this job)
  ENV               staging|prod|test
  TARGET_DATE       YYYY-MM-DD (default: yesterday in Asia/Ho_Chi_Minh)
  SYMBOL_LIST_URL   optional; default = gs://vn-market-lake-{ENV}/_ops/reference/eod-symbols.json
  CONCURRENCY       int, default 50
  RATE_PER_SOURCE   float req/s per upstream source, default 2.0
"""

import asyncio
import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import structlog
from google.cloud import storage
from shared.throttle import TokenBucket

from .corp_actions import pull_corp_actions
from .fundamentals import is_quarterly_report_date, pull_fundamentals
from .vnstock_pulls import pull_daily

log = structlog.get_logger(__name__)

DEFAULT_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _resolve_target_date() -> date:
    """Return target date from env var or yesterday in Vietnam time."""
    raw = os.environ.get("TARGET_DATE")
    if raw:
        return date.fromisoformat(raw)
    # Yesterday in Vietnam time
    now_vn = datetime.now(DEFAULT_TZ)
    return (now_vn - timedelta(days=1)).date()


def _load_symbols(storage_client: storage.Client, env: str, override_url: str | None) -> list[dict]:
    """Return list of {symbol, asset_class, exchange}.

    If SYMBOL_LIST_URL env var is set, reads that JSON. Otherwise falls back
    to a curated dev sample (used for first runs before reference job populates).
    """
    if override_url:
        bucket_name, *parts = override_url.replace("gs://", "").split("/")
        blob = storage_client.bucket(bucket_name).blob("/".join(parts))
        try:
            return json.loads(blob.download_as_text())
        except Exception as e:
            log.warning("symbol list load failed, using fallback", error=str(e))
    # Hardcoded dev fallback — small but realistic; replace with reference snapshot once available
    return [
        {"symbol": s, "asset_class": "equity", "exchange": "HOSE"}
        for s in ["VNM", "VIC", "VHM", "VPB", "TCB", "BID", "CTG", "MBB", "FPT", "MSN"]
    ]


def _upload_parquet(bucket: storage.Bucket, key: str, df: pl.DataFrame) -> None:
    """Serialize DataFrame to Parquet and upload to GCS. Overwrites existing blob."""
    buf = BytesIO()
    df.write_parquet(buf, compression="zstd", compression_level=3, statistics=True)
    bucket.blob(key).upload_from_string(
        buf.getvalue(),
        content_type="application/octet-stream",
    )


async def _process_symbol(
    sem: asyncio.Semaphore,
    bucket: storage.Bucket,
    target: dict,
    target_date: date,
    daily_tb: TokenBucket,
    fund_tb: TokenBucket,
    ca_tb: TokenBucket,
    is_q_date: bool,
) -> dict:
    """Process one symbol. Returns dict with row counts + errors."""
    sym = target["symbol"]
    out: dict = {"symbol": sym, "daily": 0, "fundamentals": 0, "corp_actions": 0, "errors": []}

    async with sem:
        # Daily OHLCV — deterministic GCS key for idempotent overwrites
        try:
            await daily_tb.acquire()
            df = await asyncio.to_thread(
                pull_daily,
                sym,
                target_date,
                target_date,
                target["asset_class"],
                target["exchange"],
            )
            if df.height > 0:
                key = (
                    f"raw/daily-ohlcv/year={target_date.year}"
                    f"/date={target_date.isoformat()}/symbol={sym}/part-0.parquet"
                )
                await asyncio.to_thread(_upload_parquet, bucket, key, df)
                out["daily"] = df.height
        except Exception as e:
            log.warning("daily pull failed", symbol=sym, error=str(e))
            out["errors"].append({"stream": "daily", "error": str(e)})

        # Fundamentals — only on quarterly filing dates
        if is_q_date:
            try:
                await fund_tb.acquire()
                df = await asyncio.to_thread(pull_fundamentals, sym)
                if df.height > 0:
                    # Use period from data if available; derive from target_date otherwise
                    if "period" in df.columns and df.height > 0:
                        quarter = df["period"][0]
                    else:
                        q_num = (target_date.month - 1) // 3 + 1
                        quarter = f"{target_date.year}-Q{q_num}"
                    key = f"raw/fundamentals/quarter={quarter}/symbol={sym}/part-0.parquet"
                    await asyncio.to_thread(_upload_parquet, bucket, key, df)
                    out["fundamentals"] = df.height
            except Exception as e:
                log.warning("fundamentals pull failed", symbol=sym, error=str(e))
                out["errors"].append({"stream": "fundamentals", "error": str(e)})

        # Corp actions — 30-day forward sweep; keyed by date for idempotency
        try:
            await ca_tb.acquire()
            df = await asyncio.to_thread(pull_corp_actions, sym, target_date)
            if df.height > 0:
                key = (
                    f"raw/corp-actions/year={target_date.year}"
                    f"/symbol={sym}/part-{target_date.isoformat()}.parquet"
                )
                await asyncio.to_thread(_upload_parquet, bucket, key, df)
                out["corp_actions"] = df.height
        except Exception as e:
            log.warning("corp_actions pull failed", symbol=sym, error=str(e))
            out["errors"].append({"stream": "corp_actions", "error": str(e)})

    return out


async def main() -> None:
    """Async entrypoint — fan-out over all symbols then emit JSON summary."""
    logging.basicConfig(level=logging.INFO)

    env = os.environ["ENV"]
    target_date = _resolve_target_date()
    concurrency = int(os.environ.get("CONCURRENCY", "50"))
    rate = float(os.environ.get("RATE_PER_SOURCE", "2.0"))
    capacity = max(1, int(rate * 5))  # 5-second burst window

    bucket_name = f"vn-market-lake-{env}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    symbols = _load_symbols(storage_client, env, os.environ.get("SYMBOL_LIST_URL"))
    log.info("eod start", env=env, date=target_date.isoformat(), n_symbols=len(symbols))

    sem = asyncio.Semaphore(concurrency)
    daily_tb = TokenBucket(rate=rate, capacity=capacity)
    fund_tb = TokenBucket(rate=rate, capacity=capacity)
    ca_tb = TokenBucket(rate=rate, capacity=capacity)
    is_q_date = is_quarterly_report_date(target_date)

    results = await asyncio.gather(
        *(
            _process_symbol(sem, bucket, t, target_date, daily_tb, fund_tb, ca_tb, is_q_date)
            for t in symbols
        )
    )

    summary = {
        "date": target_date.isoformat(),
        "env": env,
        "n_symbols": len(symbols),
        "daily_rows": sum(r["daily"] for r in results),
        "fundamentals_rows": sum(r["fundamentals"] for r in results),
        "corp_actions_rows": sum(r["corp_actions"] for r in results),
        "errors": [{"symbol": r["symbol"], **err} for r in results for err in r["errors"]],
        "ts": datetime.now(UTC).isoformat(),
    }
    # Single JSON-line to stdout — orchestration layer ingests this for monitoring
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
