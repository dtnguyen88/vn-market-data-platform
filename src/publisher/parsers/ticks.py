"""SSI tick message → Tick model.

SSI WS payload keys:
  S=symbol, P=price (1/10 VND), V=volume, T=timestamp_ms,
  MT=match_type (ATO|continuous|ATC|put-through), TID=trade_id,
  SEQ=seq, EX=exchange (HOSE|HNX|UPCoM|HNX-DERIV), SD=side (B|S|?).
"""

from datetime import datetime

from shared.schemas import AssetClass, Exchange, MatchType, Side, Tick

from .base import epoch_ms_to_dt


def parse_tick(raw: dict, ts_received: datetime) -> Tick:
    """Parse a raw SSI tick dict into a validated Tick model."""
    sym = raw["S"]
    return Tick(
        ts_event=epoch_ms_to_dt(raw["T"]),
        ts_received=ts_received,
        symbol=sym,
        asset_class=_classify(sym),
        exchange=Exchange(raw.get("EX", "HOSE")),
        price=int(raw["P"]),
        volume=int(raw["V"]),
        match_type=MatchType(raw.get("MT", "continuous")),
        side=Side(raw.get("SD", "?")),
        trade_id=str(raw["TID"]),
        seq=int(raw["SEQ"]),
    )


def _classify(symbol: str) -> AssetClass:
    """Classify a symbol as FUTURE or EQUITY based on naming conventions."""
    if symbol.startswith("VN30F") or symbol.startswith("GB"):
        return AssetClass.FUTURE
    return AssetClass.EQUITY
