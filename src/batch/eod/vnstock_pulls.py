"""Pull daily OHLCV with SSI FastConnect v3 → vnstock VCI → TCBS fallback.

Output schema matches `vnmarket.daily_ohlcv` (1/10 VND price units).
foreign_buy_vol / foreign_sell_vol are None placeholders — none of the
current sources expose them; foreign flow data planned for a later
v2 enhancement.

Primary source is SSI v3 REST since vnstock 4.x deprecated TCBS source
and its VCI parser broke on the upstream JSON shape change (2026-05).
"""

import os
import threading
from datetime import date
from typing import TYPE_CHECKING

import polars as pl
import structlog

from shared.fallback import try_in_order

if TYPE_CHECKING:
    from ssi_sdk import Auth, Data

log = structlog.get_logger(__name__)

# Module-level SSI v3 client. Lazy-init on first call; refreshed on token expiry.
# Single instance per process; protected by lock since backfill uses
# asyncio.to_thread with concurrency=2 → up to 2 threads may share this.
_ssi_lock = threading.Lock()
_ssi_auth: "Auth | None" = None
_ssi_data: "Data | None" = None


def _ensure_ssi_v3() -> "Data":
    """Lazy-init / refresh the SSI v3 sync client. Reads creds from Secret Manager."""
    global _ssi_auth, _ssi_data
    from ssi_sdk import Auth, Data  # lazy: avoids network at import time in tests

    with _ssi_lock:
        if _ssi_data is None:
            from google.cloud import secretmanager  # lazy

            project = os.environ["GCP_PROJECT_ID"]
            sm = secretmanager.SecretManagerServiceClient()

            def _sec(name: str) -> str:
                return sm.access_secret_version(
                    name=f"projects/{project}/secrets/{name}/versions/latest"
                ).payload.data.decode()

            _ssi_auth = Auth(api_key=_sec("ssi-fc-api-key"), api_secret=_sec("ssi-fc-api-secret"))
            _ssi_auth.authenticate()
            _ssi_data = Data(_ssi_auth)
        elif _ssi_auth is not None and _ssi_auth.token_manager.is_token_expired:
            _ssi_auth.refresh()
    return _ssi_data


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


def _normalize_ssi_v3(rows, symbol: str, asset_class: str, exchange: str) -> pl.DataFrame:
    """Normalize ssi_sdk OHLCData list → schema-compliant Polars frame.

    SSI v3 returns prices in whole VND; schema stores 1/10 VND so we scale x10
    (matches vnstock `_normalize` behavior for unit-compat with prior backfills).
    Date arrives as 'YYYY/MM/DD' string in `trading_date`.
    """
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(
        {
            "date": [r.trading_date for r in rows],
            "open": [int(r.open_price) for r in rows],
            "high": [int(r.high_price) for r in rows],
            "low": [int(r.low_price) for r in rows],
            "close": [int(r.close_price) for r in rows],
            "volume": [int(r.volume) for r in rows],
        }
    )
    df = df.with_columns(pl.col("date").str.strptime(pl.Date, "%Y/%m/%d"))
    for col in ("open", "high", "low", "close"):
        df = df.with_columns((pl.col(col) * 10).cast(pl.Int64).alias(col))
    df = df.with_columns(pl.col("volume").cast(pl.Int64))
    df = df.with_columns((pl.col("close") * pl.col("volume")).cast(pl.Int64).alias("value"))
    df = df.with_columns(
        [
            pl.lit(symbol).alias("symbol"),
            pl.lit(asset_class).alias("asset_class"),
            pl.lit(exchange).alias("exchange"),
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


def pull_daily_ssi_v3(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV from SSI FastConnect v3 (primary source).

    Endpoint: GET /api/v3/data/ohlc. Page size 2000 fits ~8 years of trading
    days in one request, so no pagination needed for our 2020+ backfill range.
    """
    data = _ensure_ssi_v3()
    rows = data.market_data.get_ohlc_1day_historical(
        symbol=symbol,
        from_date=start.strftime("%Y/%m/%d 00:00:00"),
        to_date=end.strftime("%Y/%m/%d 23:59:59"),
        page=1,
        size=2000,
    )
    return _normalize_ssi_v3(rows, symbol, asset_class, exchange)


def pull_daily(
    symbol: str,
    start: date,
    end: date,
    asset_class: str = "equity",
    exchange: str = "HOSE",
) -> pl.DataFrame:
    """Pull daily OHLCV with SSI v3 → vnstock VCI → TCBS fallback.

    Raises AllSourcesFailed if every source fails. SSI v3 is the canonical
    source; vnstock fallbacks remain as a backup if SSI v3 quotas/outages
    hit (and they may be broken on current vnstock versions — see notes).
    """
    log.info("pulling daily OHLCV", symbol=symbol, start=start, end=end)
    return try_in_order(
        [pull_daily_ssi_v3, pull_daily_vci, pull_daily_tcbs],
        symbol,
        start,
        end,
        asset_class,
        exchange,
    )
