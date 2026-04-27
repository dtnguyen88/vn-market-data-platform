"""SSI Level-1 quote message → QuoteL1 model.

SSI WS payload keys:
  S=symbol, T=timestamp_ms, EX=exchange,
  BP=bid_price, BV=bid_volume, AP=ask_price, AV=ask_volume.

mid_price and spread_bps are computed by QuoteL1.model_validator automatically.
"""

from datetime import datetime

from shared.schemas import Exchange, QuoteL1

from .base import epoch_ms_to_dt
from .ticks import _classify


def parse_quote_l1(raw: dict, ts_received: datetime) -> QuoteL1:
    """Parse a raw SSI L1 quote dict into a validated QuoteL1 model."""
    sym = raw["S"]
    return QuoteL1(
        ts_event=epoch_ms_to_dt(raw["T"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=_classify(sym),
        exchange=Exchange(raw.get("EX", "HOSE")),
        bid_price=int(raw.get("BP", 0)),
        bid_size=int(raw.get("BV", 0)),
        ask_price=int(raw.get("AP", 0)),
        ask_size=int(raw.get("AV", 0)),
    )
