"""Pydantic v2 schemas for SSI FastConnect v3 realtime streams.

Schema design notes (2026-05-26, post-probe):
  * Tick is a **1-second snapshot per symbol** (not per-match). SSI emits one
    `trade.<sym>` event per ~1s carrying session OHL + avg + cumulative volume
    PLUS the most-recent match (`last_price`/`last_qty`/`last_side`, zero when
    no match occurred in the window). Original "per-match" semantics retained
    via `last_*` fields, with a synthesized `trade_id` when a match is present.
  * QuoteL2 carries 10 price levels per side (server-padded with zeros). SSI
    sends `[price, volume]` pairs only — no order-count per level, so we don't
    model `bid_n_N`/`ask_n_N`.
  * Prices are stored as `int` in **whole VND** (NOT 1/10 VND as earlier docs
    claimed). Confirmed from live probe: HPG bid 24150 = 24,150 VND.
  * `IndexValue` is fed by REST polling, not the stream — SSI's WS does not
    surface realtime index value updates.

All models are frozen; datetimes timezone-aware; schema_version a ClassVar.
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
    EQUITY = "equity"
    FUTURE = "future"
    INDEX = "index"


class Exchange(StrEnum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCoM"
    HNX_DERIV = "HNX-DERIV"


class MatchType(StrEnum):
    """Auction / matching session type. Defaulted by publisher per session-time."""

    ATO = "ATO"
    CONTINUOUS = "continuous"
    ATC = "ATC"
    PUT_THROUGH = "put-through"


class Side(StrEnum):
    BUY = "B"
    SELL = "S"
    UNKNOWN = "?"


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _MarketBase(BaseModel):
    model_config = ConfigDict(frozen=True)

    ts_event: datetime = Field(description="SSI event time, Asia/Ho_Chi_Minh, second-precision")
    ts_received: datetime = Field(description="Ingest time (UTC)")
    symbol: str
    asset_class: AssetClass
    exchange: Exchange


# ---------------------------------------------------------------------------
# Tick — 1-second snapshot per symbol (session OHL + cum-vol + last match)
# ---------------------------------------------------------------------------


class Tick(_MarketBase):
    """SSI v3 1-second trade snapshot.

    `last_price`/`last_qty`/`last_side` describe the most recent match in
    the 1s window. They are zero/UNKNOWN when no match occurred — most
    events outside the match-heavy continuous phase fall into this bucket
    and are still valuable because they carry updated session OHL/avg/vol.

    `trade_id` is synthesized as `sha1(symbol|ts_event|last_price|last_qty|
    last_side)[:16]` *only* when `last_qty > 0`; otherwise None.
    """

    schema_version: ClassVar[str] = "2"  # bumped from v1 (per-match) to v2 (snapshot)

    # Session OHL + avg (all VND, int except avg which is float)
    open: int = Field(ge=0, description="Session open price")
    high: int = Field(ge=0, description="Session high price")
    low: int = Field(ge=0, description="Session low price")
    avg_price: float = Field(ge=0.0, description="Session VWAP")
    total_volume: int = Field(ge=0, description="Cumulative session volume (shares)")

    # Last match in window (0 / UNKNOWN if none)
    last_price: int = Field(ge=0, description="Last match price; 0 if no match in window")
    last_qty: int = Field(ge=0, description="Last match volume; 0 if no match in window")
    last_side: Side = Field(default=Side.UNKNOWN)
    match_type: MatchType = Field(default=MatchType.CONTINUOUS)

    trade_id: str | None = Field(
        default=None, description="sha1 of {sym|ts|p|q|si} when last_qty>0"
    )


# ---------------------------------------------------------------------------
# QuoteL1 — derived from L2[0] at parser time (no separate wire stream)
# ---------------------------------------------------------------------------


class QuoteL1(_MarketBase):
    """Best bid/ask snapshot. Mid + spread computed after construction.

    `mid_price`/`spread_bps` are None when either side is missing.
    """

    schema_version: ClassVar[str] = "1"

    bid_price: int = Field(ge=0)
    bid_size: int = Field(ge=0)
    ask_price: int = Field(ge=0)
    ask_size: int = Field(ge=0)

    mid_price: int | None = Field(default=None, ge=0)
    spread_bps: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _compute_derived(self) -> QuoteL1:
        bid, ask = self.bid_price, self.ask_price
        if bid and ask:
            mid = (bid + ask) // 2
            spread = round(10000 * (ask - bid) / mid) if mid > 0 else None
            object.__setattr__(self, "mid_price", mid)
            object.__setattr__(self, "spread_bps", spread)
        return self


# ---------------------------------------------------------------------------
# QuoteL2 — full 10-level book (40 numeric fields; SSI gives px+vol only)
# ---------------------------------------------------------------------------


def _level_fields(prefix: str) -> dict[str, tuple]:
    """Build the 20 (price, size) field declarations for one book side."""
    out: dict[str, tuple] = {}
    for i in range(1, 11):
        out[f"{prefix}_px_{i}"] = (int | None, Field(default=None, ge=0))
        out[f"{prefix}_sz_{i}"] = (int | None, Field(default=None, ge=0))
    return out


class QuoteL2(_MarketBase):
    """10-level order book snapshot. SSI sends 10 fixed levels, padded with 0s.

    A level with `bid_px_N == 0` indicates no resting order at that depth.
    """

    schema_version: ClassVar[str] = "2"  # bumped: dropped bid_n_*/ask_n_* (SSI doesn't send)

    # bid side — 10 levels of (price, size)
    bid_px_1: int | None = Field(default=None, ge=0)
    bid_sz_1: int | None = Field(default=None, ge=0)
    bid_px_2: int | None = Field(default=None, ge=0)
    bid_sz_2: int | None = Field(default=None, ge=0)
    bid_px_3: int | None = Field(default=None, ge=0)
    bid_sz_3: int | None = Field(default=None, ge=0)
    bid_px_4: int | None = Field(default=None, ge=0)
    bid_sz_4: int | None = Field(default=None, ge=0)
    bid_px_5: int | None = Field(default=None, ge=0)
    bid_sz_5: int | None = Field(default=None, ge=0)
    bid_px_6: int | None = Field(default=None, ge=0)
    bid_sz_6: int | None = Field(default=None, ge=0)
    bid_px_7: int | None = Field(default=None, ge=0)
    bid_sz_7: int | None = Field(default=None, ge=0)
    bid_px_8: int | None = Field(default=None, ge=0)
    bid_sz_8: int | None = Field(default=None, ge=0)
    bid_px_9: int | None = Field(default=None, ge=0)
    bid_sz_9: int | None = Field(default=None, ge=0)
    bid_px_10: int | None = Field(default=None, ge=0)
    bid_sz_10: int | None = Field(default=None, ge=0)
    # ask side — 10 levels of (price, size)
    ask_px_1: int | None = Field(default=None, ge=0)
    ask_sz_1: int | None = Field(default=None, ge=0)
    ask_px_2: int | None = Field(default=None, ge=0)
    ask_sz_2: int | None = Field(default=None, ge=0)
    ask_px_3: int | None = Field(default=None, ge=0)
    ask_sz_3: int | None = Field(default=None, ge=0)
    ask_px_4: int | None = Field(default=None, ge=0)
    ask_sz_4: int | None = Field(default=None, ge=0)
    ask_px_5: int | None = Field(default=None, ge=0)
    ask_sz_5: int | None = Field(default=None, ge=0)
    ask_px_6: int | None = Field(default=None, ge=0)
    ask_sz_6: int | None = Field(default=None, ge=0)
    ask_px_7: int | None = Field(default=None, ge=0)
    ask_sz_7: int | None = Field(default=None, ge=0)
    ask_px_8: int | None = Field(default=None, ge=0)
    ask_sz_8: int | None = Field(default=None, ge=0)
    ask_px_9: int | None = Field(default=None, ge=0)
    ask_sz_9: int | None = Field(default=None, ge=0)
    ask_px_10: int | None = Field(default=None, ge=0)
    ask_sz_10: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# IndexValue — populated via REST `/api/v3/data/indexSummary` polling
# ---------------------------------------------------------------------------


class IndexValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: ClassVar[str] = "1"

    ts_event: datetime
    ts_received: datetime
    index_code: str = Field(description="e.g. 'VNINDEX', 'VN30'")
    exchange: Exchange

    value: float = Field(ge=0.0)
    change: float
    change_pct: float
    total_volume: int = Field(ge=0)
    total_value: int = Field(ge=0)
    advance_count: int = Field(ge=0)
    decline_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)


# ---------------------------------------------------------------------------
# New SSI v3 streams: ForeignRoom, PutThrough, OddLot
# ---------------------------------------------------------------------------


class ForeignRoomSnapshot(_MarketBase):
    """Foreign-investor room snapshot for an equity (topic: `room.<sym>`)."""

    schema_version: ClassVar[str] = "1"

    total_room: int = Field(ge=0, description="Foreign-ownership ceiling (shares)")
    current_room: int = Field(ge=0, description="Foreign holdings (shares)")
    buy_qty: int = Field(ge=0, description="Today foreign buy volume")
    buy_value: int = Field(ge=0, description="Today foreign buy value (VND)")
    sell_qty: int = Field(ge=0)
    sell_value: int = Field(ge=0)


class PutThrough(_MarketBase):
    """Put-through (block / negotiated deal) event (topic: `put.<sym>`)."""

    schema_version: ClassVar[str] = "1"

    price: int = Field(ge=0)
    qty: int = Field(ge=0)
    total_qty: int = Field(ge=0, description="Cum put-through volume for the day")
    total_value: int = Field(ge=0, description="Cum put-through value (VND)")


class OddLotSnapshot(_MarketBase):
    """Odd-lot segment snapshot: last-match + best bid/ask (topic: `oddlot.<sym>`).

    Odd-lot books are typically very thin; we record up to 3 levels per side
    to match the depth SSI sends for this segment.
    """

    schema_version: ClassVar[str] = "1"

    last_price: int = Field(ge=0)
    last_qty: int = Field(ge=0)

    bid_px_1: int | None = Field(default=None, ge=0)
    bid_sz_1: int | None = Field(default=None, ge=0)
    bid_px_2: int | None = Field(default=None, ge=0)
    bid_sz_2: int | None = Field(default=None, ge=0)
    bid_px_3: int | None = Field(default=None, ge=0)
    bid_sz_3: int | None = Field(default=None, ge=0)
    ask_px_1: int | None = Field(default=None, ge=0)
    ask_sz_1: int | None = Field(default=None, ge=0)
    ask_px_2: int | None = Field(default=None, ge=0)
    ask_sz_2: int | None = Field(default=None, ge=0)
    ask_px_3: int | None = Field(default=None, ge=0)
    ask_sz_3: int | None = Field(default=None, ge=0)
