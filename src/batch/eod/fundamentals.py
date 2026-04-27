"""Quarterly fundamentals via vnstock with TCBS → VCI fallback.

Pulls PE, PB, EPS, BVPS, ROE, ROA, debt-to-equity, market-cap, revenue,
net-income, total-assets, total-equity for a given symbol.

NOTE: vnstock API method used here is `finance.ratio()` based on vnstock 4.x docs.
If the installed version exposes a different method name, update the source functions.
Reference: https://docs.vnstock.site/reference/finance
"""

from datetime import date

import polars as pl
import structlog
from shared.fallback import try_in_order

log = structlog.get_logger(__name__)

_FLOAT_COLS = {"pe", "pb", "eps", "bvps", "roe", "roa", "debt_to_equity"}
_INT_COLS = {"market_cap", "revenue", "net_income", "total_assets", "total_equity"}

TARGET_COLS = [
    "as_of_date",
    "symbol",
    "period",
    "pe",
    "pb",
    "eps",
    "bvps",
    "roe",
    "roa",
    "debt_to_equity",
    "market_cap",
    "revenue",
    "net_income",
    "total_assets",
    "total_equity",
]


def _normalize_fundamentals(pdf, symbol: str) -> pl.DataFrame:
    """Convert vnstock fundamentals pandas DataFrame → fundamentals schema Polars frame.

    vnstock 4.x `finance.ratio()` may return columns in varying shapes across sources.
    This function is defensive: missing columns are filled with None of the correct dtype.
    """
    df = pl.from_pandas(pdf)

    # Build period string "Q<quarter>-<year>" from year/quarter columns if present
    if "year" in df.columns and "quarter" in df.columns:
        df = df.with_columns(
            (pl.col("year").cast(pl.Utf8) + "-Q" + pl.col("quarter").cast(pl.Utf8)).alias("period")
        ).drop(["year", "quarter"])

    # Normalize date column name variants
    if "as_of_date" not in df.columns:
        for alt in ("report_date", "date", "reportDate"):
            if alt in df.columns:
                df = df.rename({alt: "as_of_date"})
                break

    df = df.with_columns(
        [
            pl.col("as_of_date").cast(pl.Date),
            pl.lit(symbol).alias("symbol"),
        ]
    )

    # Ensure all target columns exist; fill missing with None of correct dtype
    for col in TARGET_COLS:
        if col not in df.columns:
            if col in _FLOAT_COLS:
                dtype: pl.DataType = pl.Float64
            elif col in _INT_COLS:
                dtype = pl.Int64
            else:
                dtype = pl.Utf8
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(col))

    return df.select(TARGET_COLS)


def pull_fundamentals_tcbs(symbol: str) -> pl.DataFrame:
    """Pull quarterly fundamentals from TCBS via vnstock."""
    import vnstock  # lazy import: avoids network hit at import time in tests

    # TODO: verify method name against installed vnstock version
    # Reference: https://docs.vnstock.site/reference/finance
    pdf = vnstock.Vnstock().stock(symbol=symbol, source="TCBS").finance.ratio()
    return _normalize_fundamentals(pdf, symbol)


def pull_fundamentals_vci(symbol: str) -> pl.DataFrame:
    """Pull quarterly fundamentals from VCI via vnstock."""
    import vnstock  # lazy import

    pdf = vnstock.Vnstock().stock(symbol=symbol, source="VCI").finance.ratio()
    return _normalize_fundamentals(pdf, symbol)


def pull_fundamentals(symbol: str) -> pl.DataFrame:
    """Pull quarterly fundamentals with TCBS → VCI fallback.

    Raises AllSourcesFailed if every source fails.
    """
    log.info("pulling fundamentals", symbol=symbol)
    return try_in_order([pull_fundamentals_tcbs, pull_fundamentals_vci], symbol)


# Quarterly report filing-deadline calendar (approximate; operator updates yearly).
# Orchestration layer (Phase 06) uses these to decide when to trigger the puller.
# Key = quarter label, Value = (month, day) of approximate deadline.
QUARTERLY_REPORT_DATES: dict[str, tuple[int, int]] = {
    "Q1": (4, 30),  # ~Apr 30
    "Q2": (7, 30),  # ~Jul 30
    "Q3": (10, 30),  # ~Oct 30
    "Q4": (1, 30),  # ~Jan 30 of following year
}

_WINDOW_DAYS = 3  # ±3 days around each deadline is considered "on" a report date


def is_quarterly_report_date(d: date) -> bool:
    """Return True if `d` falls within ±3 days of a quarterly filing deadline.

    Used by the orchestration scheduler (Phase 06) to gate fundamentals pulls.
    """
    return any(
        d.month == month and abs(d.day - day) <= _WINDOW_DAYS
        for month, day in QUARTERLY_REPORT_DATES.values()
    )
