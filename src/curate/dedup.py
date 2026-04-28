"""Dedup helpers for curated layer.

Used by curate streams to enforce uniqueness on documented keys:
  - ticks: (symbol, ts_event, trade_id)
  - quotes/indices: (symbol, ts_event)
  - daily: (date, symbol)

Implementation uses Polars `unique` with `keep="first"`. If `sort_by` is provided,
the frame is sorted first so "first" reflects ingest order or arrival.
"""

from collections.abc import Sequence

import polars as pl


def dedup_polars(
    df: pl.DataFrame | pl.LazyFrame,
    keys: Sequence[str],
    sort_by: str | Sequence[str] | None = None,
) -> pl.DataFrame | pl.LazyFrame:
    """Drop duplicate rows by `keys` tuple, keeping first occurrence.

    If `sort_by` is given, sort ascending first so "first" is deterministic.
    Returns same type as input (DataFrame stays DataFrame; LazyFrame stays Lazy).
    """
    if sort_by is not None:
        df = df.sort(sort_by)
    return df.unique(subset=list(keys), keep="first", maintain_order=True)
