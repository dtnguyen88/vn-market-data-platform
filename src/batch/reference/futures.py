"""Futures contracts list via vnstock TCBS."""

import polars as pl
import structlog
from shared.fallback import try_in_order

log = structlog.get_logger(__name__)

_TARGET_COLS = [
    "symbol",
    "underlying_index",
    "expiry_date",
    "contract_size",
    "tick_size",
    "margin_pct",
]


def _normalize_futures(pdf) -> pl.DataFrame:
    """Normalize a pandas DataFrame from vnstock into the canonical futures_contracts schema."""
    df = pl.from_pandas(pdf)
    for c in _TARGET_COLS:
        if c not in df.columns:
            if c == "expiry_date":
                dtype = pl.Date
            elif c == "margin_pct":
                dtype = pl.Float64
            elif c in {"contract_size", "tick_size"}:
                dtype = pl.Int64
            else:
                dtype = pl.Utf8
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(c))
    if df["expiry_date"].dtype != pl.Date:
        df = df.with_columns(pl.col("expiry_date").cast(pl.Date, strict=False))
    return df.select(_TARGET_COLS)


def pull_futures_tcbs() -> pl.DataFrame:
    """Fetch futures contract list from TCBS via vnstock."""
    import vnstock

    pdf = vnstock.Vnstock().listing.future_indices()
    return _normalize_futures(pdf)


def pull_futures() -> pl.DataFrame:
    """Pull futures contracts with TCBS as sole source. Raises AllSourcesFailed if it fails."""
    return try_in_order([pull_futures_tcbs])
