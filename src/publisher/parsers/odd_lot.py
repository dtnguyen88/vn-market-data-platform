"""SSI v3 oddlot.<sym> wire dict → OddLotSnapshot.

Odd-lot book is thin (typically ≤3 levels); we record up to 3 per side.
Wire keys: s, t, p, q, bids:[[p,v]…], asks:[[p,v]…].
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import AssetClass, Exchange, OddLotSnapshot

from .base import classify_asset, default_exchange, parse_ssi_ts, to_int


def _shallow_levels(prefix: str, levels: list[Any]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for i in range(1, 4):  # 3 levels only
        if i - 1 < len(levels):
            p = to_int(levels[i - 1][0])
            s = to_int(levels[i - 1][1])
        else:
            p, s = 0, 0
        out[f"{prefix}_px_{i}"] = p if p > 0 else None
        out[f"{prefix}_sz_{i}"] = s if p > 0 else None
    return out


def parse_odd_lot(
    data: dict,
    ts_received: datetime,
    *,
    asset_class: AssetClass | None = None,
    exchange: Exchange | None = None,
) -> OddLotSnapshot:
    sym = data["s"]
    ac = asset_class or classify_asset(sym)
    ex = exchange or default_exchange(ac)
    fields = {
        "ts_event": parse_ssi_ts(data["t"]),
        "ts_received": ts_received,
        "symbol": sym,
        "asset_class": ac,
        "exchange": ex,
        "last_price": to_int(data.get("p")),
        "last_qty": to_int(data.get("q")),
        **_shallow_levels("bid", data.get("bids", [])),
        **_shallow_levels("ask", data.get("asks", [])),
    }
    return OddLotSnapshot(**fields)
