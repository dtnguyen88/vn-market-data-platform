"""Shared helpers for SSI v3 wire-dict parsers.

SSI v3 sends every numeric field as a JSON string (`"price": "27950"`), so
all parsers must coerce. Timestamps come as `"YYYY/MM/DD HH:MM:SS"` in
Asia/Ho_Chi_Minh, second-precision (no millis).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.schemas import AssetClass, Exchange, MatchType, Side

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

_SSI_TS_FMT = "%Y/%m/%d %H:%M:%S"

# Equity session windows (ICT) for ATO/ATC inference on HOSE
_ATO_START, _ATO_END = (9, 0, 0), (9, 15, 0)
_ATC_START, _ATC_END = (14, 30, 0), (14, 45, 0)


def parse_ssi_ts(raw: str) -> datetime:
    """Parse SSI 'YYYY/MM/DD HH:MM:SS' into tz-aware ICT datetime."""
    return datetime.strptime(raw, _SSI_TS_FMT).replace(tzinfo=ICT)


def to_int(v) -> int:
    """SSI numeric strings → int; tolerates empty/None → 0."""
    if v is None or v == "":
        return 0
    return int(float(v))


def to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    return float(v)


def to_side(raw: str) -> Side:
    if raw == "B":
        return Side.BUY
    if raw == "S":
        return Side.SELL
    return Side.UNKNOWN


def infer_match_type(ts: datetime) -> MatchType:
    """HOSE session-time heuristic. Cheap; correct for the majority of ticks."""
    h, m, s = ts.hour, ts.minute, ts.second
    if _ATO_START <= (h, m, s) <= _ATO_END:
        return MatchType.ATO
    if _ATC_START <= (h, m, s) <= _ATC_END:
        return MatchType.ATC
    return MatchType.CONTINUOUS


def classify_asset(symbol: str) -> AssetClass:
    """Symbol-based asset class. Cheap fallback when reference data unavailable."""
    if symbol.startswith("VN30F") or symbol.startswith("GB"):
        return AssetClass.FUTURE
    return AssetClass.EQUITY


def default_exchange(asset_class: AssetClass) -> Exchange:
    """Fallback exchange when securitiesByBoard lookup is not yet wired."""
    if asset_class is AssetClass.FUTURE:
        return Exchange.HNX_DERIV
    return Exchange.HOSE  # ~75% of volume; refine via reference data later


def synth_trade_id(
    symbol: str, ts_event: datetime, last_price: int, last_qty: int, side: Side
) -> str:
    """Deterministic short id for dedup. Empty when no match (last_qty==0)."""
    if last_qty <= 0:
        return ""
    key = f"{symbol}|{ts_event.isoformat()}|{last_price}|{last_qty}|{side.value}"
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:16]
