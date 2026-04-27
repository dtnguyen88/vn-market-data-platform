"""SSI index snapshot message → IndexValue model.

SSI WS payload keys:
  IC=index_code, T=timestamp_ms, EX=exchange,
  V=value, C=change, CP=change_pct,
  TVO=total_volume, TVA=total_value,
  ADV=advance_count, DEC=decline_count, UNC=unchanged_count.
"""

from datetime import datetime

from shared.schemas import Exchange, IndexValue

from .base import epoch_ms_to_dt


def parse_index(raw: dict, ts_received: datetime) -> IndexValue:
    """Parse a raw SSI index snapshot dict into a validated IndexValue model."""
    return IndexValue(
        ts_event=epoch_ms_to_dt(raw["T"]),
        ts_received=ts_received,
        index_code=raw["IC"],
        exchange=Exchange(raw.get("EX", "HOSE")),
        value=float(raw["V"]),
        change=float(raw["C"]),
        change_pct=float(raw["CP"]),
        total_volume=int(raw["TVO"]),
        total_value=int(raw["TVA"]),
        advance_count=int(raw["ADV"]),
        decline_count=int(raw["DEC"]),
        unchanged_count=int(raw["UNC"]),
    )
