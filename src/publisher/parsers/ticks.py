"""SSI v3 trade.<sym> wire dict → Tick.

Wire (10 keys): s, t, p, q, si, v, a, o, h, l (all JSON strings).
  p/q/si  = last-match price / quantity / aggressor side (0 / "" when none)
  a       = session VWAP (float)
  o/h/l   = session open / high / low
  v       = session cumulative volume

Each event is a 1-second snapshot; `last_qty == 0` indicates no match in the
1s window. We still emit the Tick because it carries fresh OHL + cum-vol.
"""

from __future__ import annotations

from datetime import datetime

from shared.schemas import AssetClass, Exchange, Tick

from .base import (
    classify_asset,
    default_exchange,
    infer_match_type,
    parse_ssi_ts,
    synth_trade_id,
    to_float,
    to_int,
    to_side,
)


def parse_tick(
    data: dict,
    ts_received: datetime,
    *,
    asset_class: AssetClass | None = None,
    exchange: Exchange | None = None,
) -> Tick:
    """data is the raw `data` dict from a trade.<sym> wire frame."""
    sym = data["s"]
    ts_event = parse_ssi_ts(data["t"])
    last_price = to_int(data.get("p"))
    last_qty = to_int(data.get("q"))
    last_side = to_side(data.get("si", ""))

    ac = asset_class or classify_asset(sym)
    ex = exchange or default_exchange(ac)

    trade_id = synth_trade_id(sym, ts_event, last_price, last_qty, last_side)

    return Tick(
        ts_event=ts_event,
        ts_received=ts_received,
        symbol=sym,
        asset_class=ac,
        exchange=ex,
        open=to_int(data.get("o")),
        high=to_int(data.get("h")),
        low=to_int(data.get("l")),
        avg_price=to_float(data.get("a")),
        total_volume=to_int(data.get("v")),
        last_price=last_price,
        last_qty=last_qty,
        last_side=last_side,
        match_type=infer_match_type(ts_event),
        trade_id=trade_id or None,
    )
