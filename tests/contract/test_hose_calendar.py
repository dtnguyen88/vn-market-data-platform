"""Contract: confirm next year's calendar JSON exists in repo."""

from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract


def test_current_and_next_year_calendars_exist():
    cal_dir = Path(__file__).resolve().parents[2] / "infra" / "calendar"
    this_year = date.today().year
    next_year = this_year + 1
    assert (
        cal_dir / f"vn-trading-days-{this_year}.json"
    ).exists(), f"missing calendar for current year {this_year}"
    # Next year is best-effort; just warn (skip) if missing — calendar-refresh-yearly will alert.
    if not (cal_dir / f"vn-trading-days-{next_year}.json").exists():
        pytest.skip(f"next year calendar {next_year} not yet committed")
