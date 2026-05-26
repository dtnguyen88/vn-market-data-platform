"""SSI v3 room.<sym> wire dict → ForeignRoomSnapshot.

Wire keys: s, t, tr, cr, bq, bv, sq, sv.
"""

from __future__ import annotations

from datetime import datetime

from shared.schemas import AssetClass, Exchange, ForeignRoomSnapshot

from .base import classify_asset, default_exchange, parse_ssi_ts, to_int


def parse_foreign_room(
    data: dict,
    ts_received: datetime,
    *,
    asset_class: AssetClass | None = None,
    exchange: Exchange | None = None,
) -> ForeignRoomSnapshot:
    sym = data["s"]
    ac = asset_class or classify_asset(sym)
    ex = exchange or default_exchange(ac)
    return ForeignRoomSnapshot(
        ts_event=parse_ssi_ts(data["t"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=ac,
        exchange=ex,
        total_room=to_int(data.get("tr")),
        current_room=to_int(data.get("cr")),
        buy_qty=to_int(data.get("bq")),
        buy_value=to_int(data.get("bv")),
        sell_qty=to_int(data.get("sq")),
        sell_value=to_int(data.get("sv")),
    )
