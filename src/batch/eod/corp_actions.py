"""Corp actions (dividends, splits, rights, mergers) via vnstock with TCBS → VCI fallback.

30-day forward sweep from `today` — captures upcoming ex-dates so the curated layer
can pre-compute price adjustments before the ex-date arrives.

NOTE: vnstock API methods used here:
  - TCBS: `company.dividends()` — Reference: https://docs.vnstock.site/reference/company
  - VCI:  `company.events()`   — Reference: https://docs.vnstock.site/reference/company
If the installed version exposes different method names, update the source functions.
"""

from datetime import date, timedelta

import polars as pl
import structlog
from shared.fallback import try_in_order

log = structlog.get_logger(__name__)

_FORWARD_DAYS = 30

TARGET_COLS = [
    "ex_date",
    "symbol",
    "action_type",
    "ratio",
    "amount",
    "record_date",
    "payment_date",
]

# Alternative column names that different vnstock sources may use for ex_date
_EX_DATE_ALIASES = (
    "ngay_giao_dich_khong_huong_quyen",
    "ex_dividend_date",
    "ex",
    "exDate",
)


def _normalize_corp_actions(pdf, symbol: str) -> pl.DataFrame:
    """Convert vnstock corp-actions pandas DataFrame → corp_actions schema Polars frame.

    Handles varying column name conventions across TCBS / VCI sources.
    Missing target columns are filled with None of the correct dtype.
    """
    df = pl.from_pandas(pdf)

    # Normalize ex_date column name
    if "ex_date" not in df.columns:
        for alt in _EX_DATE_ALIASES:
            if alt in df.columns:
                df = df.rename({alt: "ex_date"})
                break

    df = df.with_columns(
        [
            pl.col("ex_date").cast(pl.Date),
            pl.lit(symbol).alias("symbol"),
        ]
    )

    # Ensure all target columns exist; fill missing with None of correct dtype
    for col in TARGET_COLS:
        if col not in df.columns:
            if col in {"record_date", "payment_date"}:
                dtype: pl.DataType = pl.Date
            elif col in {"ratio", "amount"}:
                dtype = pl.Float64
            else:
                dtype = pl.Utf8
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(col))

    return df.select(TARGET_COLS)


def pull_corp_actions_tcbs(symbol: str, start: date, end: date) -> pl.DataFrame:
    """Pull corp actions from TCBS via vnstock and filter to [start, end]."""
    import vnstock  # lazy import: avoids network hit at import time in tests

    # TODO: verify method name against installed vnstock version
    # Reference: https://docs.vnstock.site/reference/company
    pdf = vnstock.Vnstock().stock(symbol=symbol, source="TCBS").company.dividends()
    df = _normalize_corp_actions(pdf, symbol)
    return df.filter((pl.col("ex_date") >= start) & (pl.col("ex_date") <= end))


def pull_corp_actions_vci(symbol: str, start: date, end: date) -> pl.DataFrame:
    """Pull corp actions from VCI via vnstock and filter to [start, end]."""
    import vnstock  # lazy import

    # TODO: verify method name against installed vnstock version
    # Reference: https://docs.vnstock.site/reference/company
    pdf = vnstock.Vnstock().stock(symbol=symbol, source="VCI").company.events()
    df = _normalize_corp_actions(pdf, symbol)
    return df.filter((pl.col("ex_date") >= start) & (pl.col("ex_date") <= end))


def pull_corp_actions(symbol: str, today: date) -> pl.DataFrame:
    """Pull corp actions with TCBS → VCI fallback using a 30-day forward sweep.

    Args:
        symbol: Ticker symbol (e.g. "VNM").
        today:  Reference date; sweep covers [today, today + 30 days].

    Raises:
        AllSourcesFailed: if every source raises an exception.
    """
    end = today + timedelta(days=_FORWARD_DAYS)
    log.info("pulling corp actions", symbol=symbol, start=today, end=end)
    return try_in_order(
        [pull_corp_actions_tcbs, pull_corp_actions_vci],
        symbol,
        today,
        end,
    )
