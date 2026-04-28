"""Derived columns for curated layer.

Currently: L1 mid_price + spread_bps. As more streams add derived cols, extend
with `add_<stream>_derived` helpers.
"""

import polars as pl


def add_l1_derived(df: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    """Add `mid_price` (int64, 1/10 VND) and `spread_bps` (int32) to an L1 frame.

    Both nullable: None when bid_price or ask_price is 0/missing.
    """
    return df.with_columns(
        mid_price=(
            pl.when((pl.col("bid_price") > 0) & (pl.col("ask_price") > 0))
            .then((pl.col("bid_price") + pl.col("ask_price")) // 2)
            .otherwise(None)
            .cast(pl.Int64)
        ),
    ).with_columns(
        spread_bps=(
            pl.when(pl.col("mid_price") > 0)
            .then(
                (10000 * (pl.col("ask_price") - pl.col("bid_price")) / pl.col("mid_price")).round()
            )
            .otherwise(None)
            .cast(pl.Int32)
        ),
    )
