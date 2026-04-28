"""Curate daily OHLCV: dedup + backward price adjustment from corp actions + write."""

import polars as pl
import structlog

from curate.adjustments import apply_adjustments
from curate.dedup import dedup_polars

log = structlog.get_logger(__name__)

_EMPTY_CORP_ACTIONS_SCHEMA = {
    "ex_date": pl.Date,
    "symbol": pl.Utf8,
    "action_type": pl.Utf8,
    "ratio": pl.Float64,
    "amount": pl.Float64,
}


def curate_daily_ohlcv(raw_uri: str, corp_actions_uri: str, curated_uri: str) -> dict:
    """Read daily OHLCV + corp actions → dedup → backward-adjust close → write curated.

    Args:
        raw_uri: Path or gs:// URI to raw daily OHLCV Parquet.
        corp_actions_uri: Path or gs:// URI to raw corp actions Parquet.
        curated_uri: Destination path or gs:// URI for curated output.

    Returns:
        Metrics dict with rows_in, rows_out, rejected.
    """
    daily_lf = pl.scan_parquet(raw_uri)
    rows_in = daily_lf.select(pl.len()).collect().item()
    deduped = dedup_polars(daily_lf, keys=["date", "symbol"], sort_by="date").collect()

    try:
        ca_df = pl.scan_parquet(corp_actions_uri).collect()
    except Exception as exc:
        log.warning("corp_actions read failed; skipping adjustments", error=str(exc))
        ca_df = pl.DataFrame(schema=_EMPTY_CORP_ACTIONS_SCHEMA)

    df = apply_adjustments(deduped, ca_df)
    df.write_parquet(curated_uri, compression="zstd", compression_level=3, statistics=True)
    log.info("curate_daily_ohlcv", rows_in=rows_in, rows_out=df.height)
    return {"rows_in": rows_in, "rows_out": df.height, "rejected": 0}
