"""Pydantic v2 schemas for the 4 VN Market realtime stream types.

Used at two boundaries:
  - publisher → Pub/Sub (serialise to JSON message body)
  - writer → schema_validator (deserialise + validate before Parquet write)

All models are frozen (immutable) so they can be used as dict keys.
All datetimes must be timezone-aware.
Numeric fields ≥ 0 except IndexValue.change / IndexValue.change_pct.

Schema version is a ClassVar — not serialised as a Pydantic field.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetClass(StrEnum):
    """Tradeable asset class on VN exchanges."""

    EQUITY = "equity"
    FUTURE = "future"
    INDEX = "index"


class Exchange(StrEnum):
    """VN exchange identifiers."""

    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCoM"
    HNX_DERIV = "HNX-DERIV"


class MatchType(StrEnum):
    """Auction / matching session type for a trade."""

    ATO = "ATO"
    CONTINUOUS = "continuous"
    ATC = "ATC"
    PUT_THROUGH = "put-through"


class Side(StrEnum):
    """Trade aggressor side."""

    BUY = "B"
    SELL = "S"
    UNKNOWN = "?"


# ---------------------------------------------------------------------------
# Shared base — common header fields across all stream types
# ---------------------------------------------------------------------------


class _MarketBase(BaseModel):
    """Common header fields shared by Tick, QuoteL1, and QuoteL2."""

    model_config = ConfigDict(frozen=True)

    ts_event: datetime = Field(description="Event timestamp (timezone-aware, Asia/Ho_Chi_Minh)")
    ts_received: datetime = Field(description="Ingest timestamp (UTC)")
    symbol: str = Field(description="Ticker symbol, e.g. 'VNM'")
    asset_class: AssetClass
    exchange: Exchange


# ---------------------------------------------------------------------------
# Tick — individual matched trade record
# ---------------------------------------------------------------------------


class Tick(_MarketBase):
    """Single matched trade event from SSI realtime feed."""

    schema_version: ClassVar[str] = "1"

    price: int = Field(ge=0, description="Trade price in 1/10 VND units")
    volume: int = Field(ge=0, description="Matched volume (shares)")
    match_type: MatchType
    side: Side
    trade_id: str = Field(description="Exchange trade id — dedup key")
    seq: int = Field(ge=0, description="SSI sequence number")


# ---------------------------------------------------------------------------
# QuoteL1 — best bid / ask snapshot with derived mid/spread
# ---------------------------------------------------------------------------


class QuoteL1(_MarketBase):
    """Level-1 quote snapshot with computed mid_price and spread_bps.

    mid_price  = (bid_price + ask_price) // 2  (None if either side missing)
    spread_bps = round(10000 * (ask_price - bid_price) / mid_price)
                 (None when mid_price is 0 or either side missing)
    """

    schema_version: ClassVar[str] = "1"

    bid_price: int = Field(ge=0)
    bid_size: int = Field(ge=0)
    ask_price: int = Field(ge=0)
    ask_size: int = Field(ge=0)

    # Computed after construction via model_validator — default None
    mid_price: int | None = Field(default=None, ge=0)
    spread_bps: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _compute_derived(self) -> QuoteL1:
        """Compute mid_price and spread_bps from bid/ask after field validation."""
        bid = self.bid_price
        ask = self.ask_price

        if bid and ask:
            mid = (bid + ask) // 2
            spread = round(10000 * (ask - bid) / mid) if mid > 0 else None
            # frozen=True: bypass immutability for internal derived fields
            object.__setattr__(self, "mid_price", mid)
            object.__setattr__(self, "spread_bps", spread)
        else:
            object.__setattr__(self, "mid_price", None)
            object.__setattr__(self, "spread_bps", None)

        return self


# ---------------------------------------------------------------------------
# QuoteL2 — full 10-level order book snapshot (60 numeric fields)
# ---------------------------------------------------------------------------


class QuoteL2(_MarketBase):
    """Level-2 order book snapshot — 10 price levels per side.

    Fields are Optional[int] because books may have fewer than 10 levels.
    bid_px_N  — bid price at level N (1=best)
    bid_sz_N  — bid size at level N
    bid_n_N   — number of orders at bid level N
    ask_px_N  — ask price at level N (1=best)
    ask_sz_N  — ask size at level N
    ask_n_N   — number of orders at ask level N
    """

    schema_version: ClassVar[str] = "1"

    # --- bid side ---
    bid_px_1: int | None = Field(default=None, ge=0)
    bid_sz_1: int | None = Field(default=None, ge=0)
    bid_n_1: int | None = Field(default=None, ge=0)

    bid_px_2: int | None = Field(default=None, ge=0)
    bid_sz_2: int | None = Field(default=None, ge=0)
    bid_n_2: int | None = Field(default=None, ge=0)

    bid_px_3: int | None = Field(default=None, ge=0)
    bid_sz_3: int | None = Field(default=None, ge=0)
    bid_n_3: int | None = Field(default=None, ge=0)

    bid_px_4: int | None = Field(default=None, ge=0)
    bid_sz_4: int | None = Field(default=None, ge=0)
    bid_n_4: int | None = Field(default=None, ge=0)

    bid_px_5: int | None = Field(default=None, ge=0)
    bid_sz_5: int | None = Field(default=None, ge=0)
    bid_n_5: int | None = Field(default=None, ge=0)

    bid_px_6: int | None = Field(default=None, ge=0)
    bid_sz_6: int | None = Field(default=None, ge=0)
    bid_n_6: int | None = Field(default=None, ge=0)

    bid_px_7: int | None = Field(default=None, ge=0)
    bid_sz_7: int | None = Field(default=None, ge=0)
    bid_n_7: int | None = Field(default=None, ge=0)

    bid_px_8: int | None = Field(default=None, ge=0)
    bid_sz_8: int | None = Field(default=None, ge=0)
    bid_n_8: int | None = Field(default=None, ge=0)

    bid_px_9: int | None = Field(default=None, ge=0)
    bid_sz_9: int | None = Field(default=None, ge=0)
    bid_n_9: int | None = Field(default=None, ge=0)

    bid_px_10: int | None = Field(default=None, ge=0)
    bid_sz_10: int | None = Field(default=None, ge=0)
    bid_n_10: int | None = Field(default=None, ge=0)

    # --- ask side ---
    ask_px_1: int | None = Field(default=None, ge=0)
    ask_sz_1: int | None = Field(default=None, ge=0)
    ask_n_1: int | None = Field(default=None, ge=0)

    ask_px_2: int | None = Field(default=None, ge=0)
    ask_sz_2: int | None = Field(default=None, ge=0)
    ask_n_2: int | None = Field(default=None, ge=0)

    ask_px_3: int | None = Field(default=None, ge=0)
    ask_sz_3: int | None = Field(default=None, ge=0)
    ask_n_3: int | None = Field(default=None, ge=0)

    ask_px_4: int | None = Field(default=None, ge=0)
    ask_sz_4: int | None = Field(default=None, ge=0)
    ask_n_4: int | None = Field(default=None, ge=0)

    ask_px_5: int | None = Field(default=None, ge=0)
    ask_sz_5: int | None = Field(default=None, ge=0)
    ask_n_5: int | None = Field(default=None, ge=0)

    ask_px_6: int | None = Field(default=None, ge=0)
    ask_sz_6: int | None = Field(default=None, ge=0)
    ask_n_6: int | None = Field(default=None, ge=0)

    ask_px_7: int | None = Field(default=None, ge=0)
    ask_sz_7: int | None = Field(default=None, ge=0)
    ask_n_7: int | None = Field(default=None, ge=0)

    ask_px_8: int | None = Field(default=None, ge=0)
    ask_sz_8: int | None = Field(default=None, ge=0)
    ask_n_8: int | None = Field(default=None, ge=0)

    ask_px_9: int | None = Field(default=None, ge=0)
    ask_sz_9: int | None = Field(default=None, ge=0)
    ask_n_9: int | None = Field(default=None, ge=0)

    ask_px_10: int | None = Field(default=None, ge=0)
    ask_sz_10: int | None = Field(default=None, ge=0)
    ask_n_10: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# IndexValue — index snapshot (VNINDEX, VN30, etc.)
# ---------------------------------------------------------------------------


class IndexValue(BaseModel):
    """Index snapshot — no symbol/asset_class/exchange header like equity streams."""

    model_config = ConfigDict(frozen=True)

    schema_version: ClassVar[str] = "1"

    ts_event: datetime = Field(description="Event timestamp (timezone-aware)")
    ts_received: datetime = Field(description="Ingest timestamp (UTC)")
    index_code: str = Field(description="Index code, e.g. 'VNINDEX', 'VN30'")
    exchange: Exchange

    value: float = Field(ge=0.0, description="Index value in points")
    # change and change_pct can be negative — no ge constraint
    change: float = Field(description="Point change from prior close")
    change_pct: float = Field(description="Percentage change from prior close")

    total_volume: int = Field(ge=0, description="Total market volume")
    total_value: int = Field(ge=0, description="Total market value in VND")

    advance_count: int = Field(ge=0, description="Number of advancing issues")
    decline_count: int = Field(ge=0, description="Number of declining issues")
    unchanged_count: int = Field(ge=0, description="Number of unchanged issues")
