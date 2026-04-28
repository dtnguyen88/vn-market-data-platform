"""Curate ticks: dedup + write."""

import polars as pl
import structlog

from curate.dedup import dedup_polars

log = structlog.get_logger(__name__)


def curate_ticks(raw_uri: str, curated_uri: str) -> dict:
    """Read ticks raw → dedup → write curated. Returns metrics."""
    lf = pl.scan_parquet(raw_uri)
    rows_in = lf.select(pl.len()).collect().item()
    df = dedup_polars(lf, keys=["symbol", "ts_event", "trade_id"], sort_by="ts_event").collect(
        engine="streaming"
    )
    df.write_parquet(curated_uri, compression="zstd", compression_level=3, statistics=True)
    log.info("curate_ticks", rows_in=rows_in, rows_out=df.height)
    return {"rows_in": rows_in, "rows_out": df.height, "rejected": 0}
