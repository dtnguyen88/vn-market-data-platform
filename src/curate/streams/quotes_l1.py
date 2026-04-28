"""Curate L1 quotes: dedup + derived columns (mid_price, spread_bps) + write."""

import polars as pl
import structlog

from curate.dedup import dedup_polars
from curate.derived_columns import add_l1_derived

log = structlog.get_logger(__name__)


def curate_quotes_l1(raw_uri: str, curated_uri: str) -> dict:
    """Read L1 quotes raw → dedup → add derived cols → write curated. Returns metrics."""
    lf = pl.scan_parquet(raw_uri)
    rows_in = lf.select(pl.len()).collect().item()
    deduped = dedup_polars(lf, keys=["symbol", "ts_event"], sort_by="ts_event")
    derived = add_l1_derived(deduped)
    df = derived.collect(engine="streaming")
    df.write_parquet(curated_uri, compression="zstd", compression_level=3, statistics=True)
    log.info("curate_quotes_l1", rows_in=rows_in, rows_out=df.height)
    return {"rows_in": rows_in, "rows_out": df.height, "rejected": 0}
