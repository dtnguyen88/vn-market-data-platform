"""Ticker master via vnstock with TCBS->VCI fallback."""

import polars as pl
import structlog
from shared.fallback import try_in_order

log = structlog.get_logger(__name__)

_TARGET_COLS = [
    "symbol",
    "name",
    "exchange",
    "asset_class",
    "sector_l1",
    "sector_l2",
    "industry",
    "listed_date",
    "status",
    "lot_size",
    "tick_size",
    "foreign_room_pct",
]


def _normalize_tickers(pdf) -> pl.DataFrame:
    """Normalize a pandas DataFrame from vnstock into the canonical tickers schema."""
    df = pl.from_pandas(pdf)
    for c in _TARGET_COLS:
        if c not in df.columns:
            if c == "listed_date":
                dtype = pl.Date
            elif c == "foreign_room_pct":
                dtype = pl.Float64
            elif c in {"lot_size", "tick_size"}:
                dtype = pl.Int64
            else:
                dtype = pl.Utf8
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(c))
    if df["listed_date"].dtype != pl.Date:
        df = df.with_columns(pl.col("listed_date").cast(pl.Date, strict=False))
    return df.select(_TARGET_COLS)


def pull_tickers_tcbs() -> pl.DataFrame:
    """Fetch ticker master from TCBS via vnstock."""
    import vnstock

    pdf = vnstock.Vnstock().listing.symbols_by_industries()
    return _normalize_tickers(pdf)


def pull_tickers_vci() -> pl.DataFrame:
    """Fetch ticker master from VCI via vnstock (fallback)."""
    import vnstock

    pdf = vnstock.Vnstock(source="VCI").listing.symbols_by_exchange()
    return _normalize_tickers(pdf)


def pull_tickers() -> pl.DataFrame:
    """Pull ticker master with TCBS->VCI fallback. Raises AllSourcesFailed if all fail."""
    return try_in_order([pull_tickers_tcbs, pull_tickers_vci])
