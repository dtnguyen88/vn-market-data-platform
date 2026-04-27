"""SSI Level-2 orderbook message → QuoteL2 model.

SSI WS payload keys:
  S=symbol, T=timestamp_ms, EX=exchange,
  B=[{P, V, N}, ...up to 10 levels] (bids),
  A=[{P, V, N}, ...up to 10 levels] (asks).

Flattens nested arrays into the QuoteL2 flat schema (bid_px_1..bid_px_10, etc.).
Missing levels (partial book) are mapped to None.
"""

from datetime import datetime

from shared.schemas import Exchange, QuoteL2

from .base import epoch_ms_to_dt
from .ticks import _classify


def parse_quote_l2(raw: dict, ts_received: datetime) -> QuoteL2:
    """Parse a raw SSI L2 orderbook dict into a validated QuoteL2 model."""
    sym = raw["S"]
    bids = raw.get("B", [])
    asks = raw.get("A", [])

    fields: dict = {}
    for i in range(10):
        b = bids[i] if i < len(bids) else None
        a = asks[i] if i < len(asks) else None
        fields[f"bid_px_{i + 1}"] = int(b["P"]) if b else None
        fields[f"bid_sz_{i + 1}"] = int(b["V"]) if b else None
        fields[f"bid_n_{i + 1}"] = int(b["N"]) if b else None
        fields[f"ask_px_{i + 1}"] = int(a["P"]) if a else None
        fields[f"ask_sz_{i + 1}"] = int(a["V"]) if a else None
        fields[f"ask_n_{i + 1}"] = int(a["N"]) if a else None

    return QuoteL2(
        ts_event=epoch_ms_to_dt(raw["T"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=_classify(sym),
        exchange=Exchange(raw.get("EX", "HOSE")),
        **fields,
    )
