"""SSI v3 quote.<sym> wire dict → QuoteL1 (best bid/ask only).

L1 is derived from L2 wire data — SSI doesn't emit a separate L1 stream.
This parser produces a QuoteL1 in parallel with the QuoteL2 produced by
quotes_l2 (publisher publishes to both topics from one wire frame).
"""

from __future__ import annotations

from datetime import datetime

from shared.schemas import AssetClass, Exchange, QuoteL1

from .base import classify_asset, default_exchange, parse_ssi_ts, to_int


def parse_quote_l1(
    data: dict,
    ts_received: datetime,
    *,
    asset_class: AssetClass | None = None,
    exchange: Exchange | None = None,
) -> QuoteL1:
    sym = data["s"]
    ac = asset_class or classify_asset(sym)
    ex = exchange or default_exchange(ac)

    bids = data.get("bids") or [[0, 0]]
    asks = data.get("asks") or [[0, 0]]

    return QuoteL1(
        ts_event=parse_ssi_ts(data["t"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=ac,
        exchange=ex,
        bid_price=to_int(bids[0][0]),
        bid_size=to_int(bids[0][1]),
        ask_price=to_int(asks[0][0]),
        ask_size=to_int(asks[0][1]),
    )
