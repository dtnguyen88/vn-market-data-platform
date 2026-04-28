"""Curate fundamentals: dedup by (symbol, period) sorted by as_of_date + write."""

import polars as pl
import structlog

from curate.dedup import dedup_polars

log = structlog.get_logger(__name__)


def curate_fundamentals(raw_uri: str, curated_uri: str) -> dict:
    """Read fundamentals raw → dedup → write curated. Returns metrics."""
    lf = pl.scan_parquet(raw_uri)
    rows_in = lf.select(pl.len()).collect().item()
    df = dedup_polars(lf, keys=["symbol", "period"], sort_by="as_of_date").collect()
    df.write_parquet(curated_uri, compression="zstd", compression_level=3, statistics=True)
    log.info("curate_fundamentals", rows_in=rows_in, rows_out=df.height)
    return {"rows_in": rows_in, "rows_out": df.height, "rejected": 0}
