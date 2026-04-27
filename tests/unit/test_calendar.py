"""Unit tests for shared.calendar — local file path only."""

from datetime import date, time
from pathlib import Path

import pytest
from shared.calendar import AssetClass, Calendar

FIXTURE = Path(__file__).parent.parent / "fixtures" / "calendar" / "2026.json"


@pytest.fixture
def cal():
    return Calendar.from_file(FIXTURE)


@pytest.mark.unit
def test_is_trading_day_true(cal):
    assert cal.is_trading_day(date(2026, 1, 2)) is True


@pytest.mark.unit
def test_is_trading_day_false_holiday(cal):
    assert cal.is_trading_day(date(2026, 4, 30)) is False  # Reunification Day


@pytest.mark.unit
def test_is_trading_day_false_weekend(cal):
    assert cal.is_trading_day(date(2026, 1, 3)) is False  # Saturday


@pytest.mark.unit
def test_get_sessions_equity(cal):
    sessions = cal.get_sessions(AssetClass.EQUITY)
    assert sessions == [(time(9, 0), time(11, 30)), (time(13, 0), time(14, 45))]


@pytest.mark.unit
def test_get_sessions_derivative_starts_at_0845(cal):
    sessions = cal.get_sessions(AssetClass.DERIVATIVE)
    assert sessions[0][0] == time(8, 45)


@pytest.mark.unit
def test_holiday_name(cal):
    assert cal.holiday_name(date(2026, 4, 30)) == "Reunification Day"
    assert cal.holiday_name(date(2026, 1, 2)) is None
