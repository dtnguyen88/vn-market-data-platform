"""Backfill Cloud Run Job. Pulls historical data and lands raw partitions.

For ticks/quotes/indices, attempts SSI historical; on NotAvailableError records
a permanent gap to _ops/permanent-gaps/{stream}.jsonl (SSI stubs — leave alone).

For daily/fundamentals/corp_actions/reference, uses real vnstock pullers with
source=vnstock Hive partition for future SSI-FC swap-in.

GCS path scheme:
  raw/daily-ohlcv/source=vnstock/year=Y/date=D/symbol=S/part-0.parquet
  raw/fundamentals/source=vnstock/quarter=Q/symbol=S/part-0.parquet
  raw/corp-actions/source=vnstock/year=Y/symbol=S/part-{chunk_start}.parquet
  raw/reference/tickers/source=vnstock/snapshot=D/part-0.parquet
  raw/reference/futures/source=vnstock/snapshot=D/part-0.parquet

Args/env:
  --start YYYY-MM-DD --end YYYY-MM-DD --streams=daily,fundamentals,...
  CLOUD_RUN_TASK_INDEX, CLOUD_RUN_TASK_COUNT  (auto-set by Cloud Run Jobs)
  GCP_PROJECT_ID, ENV
"""

import argparse
import asyncio
import json
import os
from datetime import UTC, date, datetime
from io import BytesIO

import polars as pl
import structlog
from shared.fallback import try_in_order
from shared.throttle import TokenBucket

from .history_clients import (
    NotAvailableError,
    pull_history_indices,
    pull_history_quotes_l1,
    pull_history_quotes_l2,
    pull_history_ticks,
)
from .planner import plan_chunks

log = structlog.get_logger(__name__)

HISTORICAL_STREAMS = {
    "ticks": pull_history_ticks,
    "quotes-l1": pull_history_quotes_l1,
    "quotes-l2": pull_history_quotes_l2,
    "indices": pull_history_indices,
}

_FALLBACK_SYMBOLS = [
    "VNM",
    "VIC",
    "VHM",
    "VPB",
    "TCB",
    "BID",
    "CTG",
    "MBB",
    "FPT",
    "MSN",
    "HPG",
    "GAS",
    "VRE",
    "NVL",
    "PLX",
    "SAB",
    "STB",
    "VJC",
    "POW",
    "ACB",
    "SSI",
    "HDB",
    "TPB",
    "MWG",
    "BVH",
    "KDH",
    "REE",
    "DPM",
    "GVR",
    "PNJ",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_backfill_symbols(env: str) -> list[str]:
    """Load symbol list from GCS or fall back to hardcoded VN30-style list."""
    from google.cloud import storage  # lazy — avoids module-level network in tests

    try:
        client = storage.Client()
        bucket_name = f"vn-market-lake-{env}"
        blob = client.bucket(bucket_name).blob("_ops/reference/eod-symbols.json")
        data = json.loads(blob.download_as_text())
        # data may be list[str] or list[dict]
        if data and isinstance(data[0], dict):
            return [item["symbol"] for item in data]
        return [str(s) for s in data]
    except Exception as e:
        log.warning("symbol list load failed, using fallback", error=str(e))
        return list(_FALLBACK_SYMBOLS)


def _upload_parquet(bucket, key: str, df: pl.DataFrame) -> None:
    """Serialize DataFrame to Parquet and upload to GCS (overwrites)."""
    buf = BytesIO()
    df.write_parquet(buf, compression="zstd", compression_level=3, statistics=True)
    bucket.blob(key).upload_from_string(buf.getvalue(), content_type="application/octet-stream")


def _record_permanent_gap(
    project_id: str, env: str, stream: str, start: date, end: date, reason: str
) -> None:
    from google.cloud import storage  # lazy

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


# ---------------------------------------------------------------------------
# Per-stream async workers
# ---------------------------------------------------------------------------


async def _run_daily(
    sem: asyncio.Semaphore,
    bucket,
    symbol: str,
    chunk_start: date,
    chunk_end: date,
    tb: TokenBucket,
) -> tuple[int, list[str]]:
    """Pull daily OHLCV for one symbol across chunk range; write one Parquet per date."""
    from batch.eod.vnstock_pulls import pull_daily  # lazy

    # Symbol-pattern → asset_class/exchange. VN30F* are derivatives traded on HNX.
    if symbol.startswith("VN30F"):
        asset_class, exchange = "future", "HNX"
    else:
        asset_class, exchange = "equity", "HOSE"

    rows = 0
    errors: list[str] = []
    async with sem:
        try:
            await tb.acquire()
            df = await asyncio.to_thread(
                pull_daily, symbol, chunk_start, chunk_end, asset_class, exchange
            )
            if df.height == 0:
                return rows, errors
            # Group by date and parallel-upload one file per (date, symbol).
            # GCS uploads aren't rate-limited by vnstock; fan out to cut wall time
            # from sequential 1300 x 100ms = 130s per symbol to ~5s.
            upload_tasks = []
            for d_val, group in df.group_by("date"):
                d = d_val[0] if isinstance(d_val, tuple) else d_val
                if hasattr(d, "isoformat"):
                    d_str = d.isoformat()
                    y = d.year
                else:
                    d_str = str(d)
                    y = str(d)[:4]
                key = (
                    f"raw/daily-ohlcv/source=vnstock/year={y}"
                    f"/date={d_str}/symbol={symbol}/part-0.parquet"
                )
                upload_tasks.append(asyncio.to_thread(_upload_parquet, bucket, key, group))
                rows += group.height
            await asyncio.gather(*upload_tasks)
        except Exception as e:
            log.warning("daily pull failed", symbol=symbol, error=str(e))
            errors.append(f"{symbol}: {e}")
    return rows, errors


async def _run_fundamentals(
    sem: asyncio.Semaphore,
    bucket,
    symbol: str,
    chunk_start: date,
    chunk_end: date,
    tb: TokenBucket,
) -> tuple[int, list[str]]:
    """Pull full fundamentals history for one symbol; filter to chunk range by as_of_date."""
    from batch.eod.fundamentals import pull_fundamentals  # lazy

    rows = 0
    errors: list[str] = []
    async with sem:
        try:
            await tb.acquire()
            df = await asyncio.to_thread(pull_fundamentals, symbol)
            if df.height == 0:
                return rows, errors
            # Filter to chunk date range
            df = df.filter(
                (pl.col("as_of_date") >= chunk_start) & (pl.col("as_of_date") <= chunk_end)
            )
            if df.height == 0:
                return rows, errors
            # Parallel-upload one file per (period, symbol)
            upload_tasks = []
            for (period_val,), group in df.group_by("period"):
                period_str = str(period_val) if period_val is not None else "unknown"
                key = (
                    f"raw/fundamentals/source=vnstock"
                    f"/quarter={period_str}/symbol={symbol}/part-0.parquet"
                )
                upload_tasks.append(asyncio.to_thread(_upload_parquet, bucket, key, group))
                rows += group.height
            await asyncio.gather(*upload_tasks)
        except Exception as e:
            log.warning("fundamentals pull failed", symbol=symbol, error=str(e))
            errors.append(f"{symbol}: {e}")
    return rows, errors


async def _run_corp_actions(
    sem: asyncio.Semaphore,
    bucket,
    symbol: str,
    chunk_start: date,
    chunk_end: date,
    tb: TokenBucket,
) -> tuple[int, list[str]]:
    """Pull corp actions for one symbol; write one Parquet per (year, symbol)."""
    from batch.eod.corp_actions import pull_corp_actions_tcbs, pull_corp_actions_vci  # lazy

    rows = 0
    errors: list[str] = []
    chunk_start_iso = chunk_start.isoformat()
    async with sem:
        try:
            await tb.acquire()
            df = await asyncio.to_thread(
                try_in_order,
                [pull_corp_actions_tcbs, pull_corp_actions_vci],
                symbol,
                chunk_start,
                chunk_end,
            )
            if df.height == 0:
                return rows, errors
            # Parallel-upload one file per (year, symbol)
            df = df.with_columns(pl.col("ex_date").dt.year().alias("_year"))
            upload_tasks = []
            for (year_val,), group in df.group_by("_year"):
                group = group.drop("_year")
                key = (
                    f"raw/corp-actions/source=vnstock/year={year_val}"
                    f"/symbol={symbol}/part-{chunk_start_iso}.parquet"
                )
                upload_tasks.append(asyncio.to_thread(_upload_parquet, bucket, key, group))
                rows += group.height
            await asyncio.gather(*upload_tasks)
        except Exception as e:
            log.warning("corp_actions pull failed", symbol=symbol, error=str(e))
            errors.append(f"{symbol}: {e}")
    return rows, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


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

    asyncio.run(_async_main(summary, streams, chunk_start, chunk_end, project_id, env, task_index))
    print(json.dumps(summary))


async def _async_main(
    summary: dict,
    streams: list[str],
    chunk_start: date,
    chunk_end: date,
    project_id: str,
    env: str,
    task_index: int,
) -> None:
    from google.cloud import storage  # lazy

    # vnstock community = 20 req/min hard limit per IP. Keep aggregate well under.
    # Single shared bucket across all streams: 18 req/min (rate=0.3, capacity=1).
    concurrency = 2
    sem = asyncio.Semaphore(concurrency)
    shared_tb = TokenBucket(rate=0.3, capacity=1)
    daily_tb = shared_tb
    fund_tb = shared_tb
    ca_tb = shared_tb

    bucket_name = f"vn-market-lake-{env}"
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)

    chunk_end_iso = chunk_end.isoformat()

    for stream in streams:
        if stream in HISTORICAL_STREAMS:
            try:
                _ = HISTORICAL_STREAMS[stream]("VNM", chunk_start, chunk_end)
                summary["results"][stream] = {"rows": 0, "errors": []}
            except NotAvailableError as e:
                _record_permanent_gap(project_id, env, stream, chunk_start, chunk_end, str(e))
                summary["results"][stream] = {"rows": 0, "errors": [f"gap-recorded: {e}"]}
            except Exception as e:
                summary["results"][stream] = {"rows": 0, "errors": [str(e)]}

        elif stream == "daily":
            symbols = _load_backfill_symbols(env)
            tasks = [
                _run_daily(sem, bucket, sym, chunk_start, chunk_end, daily_tb) for sym in symbols
            ]
            results = await asyncio.gather(*tasks)
            total_rows = sum(r for r, _ in results)
            all_errors = [e for _, errs in results for e in errs]
            summary["results"]["daily"] = {"rows": total_rows, "errors": all_errors}

        elif stream == "fundamentals":
            if task_index != 0:
                summary["results"]["fundamentals"] = {
                    "rows": 0,
                    "errors": [],
                    "skipped": "non-zero task",
                }
                continue
            symbols = _load_backfill_symbols(env)
            tasks = [
                _run_fundamentals(sem, bucket, sym, chunk_start, chunk_end, fund_tb)
                for sym in symbols
            ]
            results = await asyncio.gather(*tasks)
            total_rows = sum(r for r, _ in results)
            all_errors = [e for _, errs in results for e in errs]
            summary["results"]["fundamentals"] = {"rows": total_rows, "errors": all_errors}

        elif stream == "corp_actions":
            symbols = _load_backfill_symbols(env)
            tasks = [
                _run_corp_actions(sem, bucket, sym, chunk_start, chunk_end, ca_tb)
                for sym in symbols
            ]
            results = await asyncio.gather(*tasks)
            total_rows = sum(r for r, _ in results)
            all_errors = [e for _, errs in results for e in errs]
            summary["results"]["corp_actions"] = {"rows": total_rows, "errors": all_errors}

        elif stream == "reference":
            if task_index != 0:
                summary["results"]["reference"] = {
                    "rows": 0,
                    "errors": [],
                    "skipped": "non-zero task",
                }
                continue
            from batch.reference.futures import pull_futures  # lazy
            from batch.reference.tickers import pull_tickers  # lazy

            ref_rows = 0
            ref_errors: list[str] = []
            try:
                df_tickers = await asyncio.to_thread(pull_tickers)
                key = (
                    f"raw/reference/tickers/source=vnstock/snapshot={chunk_end_iso}/part-0.parquet"
                )
                await asyncio.to_thread(_upload_parquet, bucket, key, df_tickers)
                ref_rows += df_tickers.height
            except Exception as e:
                log.warning("reference tickers pull failed", error=str(e))
                ref_errors.append(f"tickers: {e}")
            try:
                df_futures = await asyncio.to_thread(pull_futures)
                key = (
                    f"raw/reference/futures/source=vnstock/snapshot={chunk_end_iso}/part-0.parquet"
                )
                await asyncio.to_thread(_upload_parquet, bucket, key, df_futures)
                ref_rows += df_futures.height
            except Exception as e:
                log.warning("reference futures pull failed", error=str(e))
                ref_errors.append(f"futures: {e}")
            summary["results"]["reference"] = {"rows": ref_rows, "errors": ref_errors}

        else:
            summary["results"][stream] = {"rows": 0, "errors": [f"unknown stream: {stream}"]}


if __name__ == "__main__":
    main()
