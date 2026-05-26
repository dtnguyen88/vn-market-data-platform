"""SSI v3 put.<sym> wire dict → PutThrough (block / negotiated deal)."""

from __future__ import annotations

from datetime import datetime

from shared.schemas import AssetClass, Exchange, PutThrough

from .base import classify_asset, default_exchange, parse_ssi_ts, to_int


def parse_put_through(
    data: dict,
    ts_received: datetime,
    *,
    asset_class: AssetClass | None = None,
    exchange: Exchange | None = None,
) -> PutThrough:
    sym = data["s"]
    ac = asset_class or classify_asset(sym)
    ex = exchange or default_exchange(ac)
    return PutThrough(
        ts_event=parse_ssi_ts(data["t"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=ac,
        exchange=ex,
        price=to_int(data.get("p")),
        qty=to_int(data.get("q")),
        total_qty=to_int(data.get("tq")),
        total_value=to_int(data.get("tv")),
    )
