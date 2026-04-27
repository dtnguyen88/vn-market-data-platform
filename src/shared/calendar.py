"""Trading calendar — VN exchanges (HOSE/HNX/UPCoM + derivatives).

Single source of truth: infra/calendar/vn-trading-days-{year}.json (in repo).
Runtime read: gs://vn-market-lake-{env}/_ops/calendar/{year}.json (deployed by Terraform).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
from pathlib import Path


class AssetClass(StrEnum):
    EQUITY = "equity"
    DERIVATIVE = "derivative"


@dataclass(frozen=True)
class Calendar:
    year: int
    trading_days: frozenset[date]
    holidays: dict[date, str]
    sessions: dict[AssetClass, list[tuple[time, time]]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Calendar:
        return cls(
            year=int(data["year"]),
            trading_days=frozenset(date.fromisoformat(d) for d in data["trading_days"]),
            holidays={date.fromisoformat(h["date"]): h["name"] for h in data["holidays"]},
            sessions={
                AssetClass(k): [(_parse_time(s[0]), _parse_time(s[1])) for s in v]
                for k, v in data["sessions"].items()
            },
        )

    @classmethod
    def from_file(cls, path: Path | str) -> Calendar:
        return cls.from_dict(json.loads(Path(path).read_text()))

    def is_trading_day(self, d: date) -> bool:
        return d in self.trading_days

    def holiday_name(self, d: date) -> str | None:
        return self.holidays.get(d)

    def get_sessions(self, asset_class: AssetClass) -> list[tuple[time, time]]:
        return list(self.sessions.get(asset_class, []))

    def is_in_session(self, asset_class: AssetClass, t: datetime) -> bool:
        if not self.is_trading_day(t.date()):
            return False
        wall = t.time()
        return any(start <= wall <= end for start, end in self.get_sessions(asset_class))


def _parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))
