"""Pull daily OHLCV via vnstock with TCBS → VCI → SSI fallback.

Output schema matches `vnmarket.daily_ohlcv` (1/10 VND price units).
foreign_buy_vol / foreign_sell_vol are None placeholders — vnstock free tier
does not expose them; foreign flow data planned for a later v2 enhancement.
"""

from datetime import date

import polars as pl
import structlog
from shared.fallback import try_in_order

log = structlog.get_logger(__name__)


def _normalize(pdf, symbol: str, asset_class: str, exchange: str) -> pl.DataFrame:
    """Normalize a pandas DataFrame from vnstock → schema-compliant Polars frame.

    vnstock returns prices in VND; schema stores 1/10 VND so we multiply by 10.
    """
    df = pl.from_pandas(pdf)
    # vnstock columns: time, open, high, low, close, volume
    df = df.rename({"time": "date"})
    # Cast date column from Datetime → date (vnstock returns datetime64)
    df = df.with_columns(pl.col("date").dt.date())
    # Scale prices: vnstock VND → 1/10 VND
    for col in ("open", "high", "low", "close"):
        df = df.with_columns((pl.col(col) * 10).cast(pl.Int64).alias(col))
    df = df.with_columns(pl.col("volume").cast(pl.Int64))
    # Derivative: value = close * volume
    df = df.with_columns((pl.col("close") * pl.col("volume")).cast(pl.Int64).alias("value"))
    # Static metadata columns
    df = df.with_columns(
        [
            pl.lit(symbol).alias("symbol"),
            pl.lit(asset_class).alias("asset_class"),
            pl.lit(exchange).alias("exchange"),
            # Stubbed: vnstock free tier does not expose foreign flow volumes
            pl.lit(None, dtype=pl.Int64).alias("foreign_buy_vol"),
            pl.lit(None, dtype=pl.Int64).alias("foreign_sell_vol"),
        ]
    )
    return df.select(
        [
            "date",
            "symbol",
            "asset_class",
            "exchange",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
            "foreign_buy_vol",
            "foreign_sell_vol",
        ]
    )


def pull_daily_tcbs(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV from TCBS via vnstock."""
    import vnstock  # lazy import: avoids network hit at import time in tests

    pdf = (
        vnstock.Vnstock()
        .stock(symbol=symbol, source="TCBS")
        .quote.history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1D",
        )
    )
    return _normalize(pdf, symbol, asset_class, exchange)


def pull_daily_vci(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV from VCI via vnstock."""
    import vnstock  # lazy import

    pdf = (
        vnstock.Vnstock()
        .stock(symbol=symbol, source="VCI")
        .quote.history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1D",
        )
    )
    return _normalize(pdf, symbol, asset_class, exchange)


def pull_daily_ssi(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV from SSI (MSN proxy) via vnstock.

    vnstock 4.x exposes SSI data via source="MSN" (SSI HTML-style proxy).
    If the installed version uses a different source key, update accordingly.
    """
    import vnstock  # lazy import

    pdf = (
        vnstock.Vnstock()
        .stock(symbol=symbol, source="MSN")
        .quote.history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1D",
        )
    )
    return _normalize(pdf, symbol, asset_class, exchange)


def pull_daily(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV with TCBS → VCI → SSI fallback.

    Raises AllSourcesFailed if every source fails.
    """
    log.info("pulling daily OHLCV", symbol=symbol, start=start, end=end)
    return try_in_order(
        [pull_daily_tcbs, pull_daily_vci, pull_daily_ssi],
        symbol,
        start,
        end,
        asset_class,
        exchange,
    )
