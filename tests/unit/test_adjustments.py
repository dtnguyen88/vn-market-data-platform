"""Unit tests for curate.adjustments."""

from datetime import date

import polars as pl
import pytest
from curate.adjustments import _action_factor, apply_adjustments


@pytest.mark.unit
def test_no_corp_actions_passthrough():
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 3)],
            "symbol": ["VNM", "VNM"],
            "close": [850000, 855000],
        }
    )
    actions = pl.DataFrame(
        schema={
            "ex_date": pl.Date,
            "symbol": pl.Utf8,
            "action_type": pl.Utf8,
            "ratio": pl.Float64,
            "amount": pl.Float64,
        }
    )
    result = apply_adjustments(daily, actions)
    assert result["adj_close"].to_list() == [850000, 855000]


@pytest.mark.unit
def test_split_2_for_1_halves_prior_close():
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            "symbol": ["VNM", "VNM", "VNM"],
            "close": [1_000_000, 1_010_000, 500_000],  # split happened on 1/4
        }
    )
    actions = pl.DataFrame(
        {
            "ex_date": [date(2024, 1, 4)],
            "symbol": ["VNM"],
            "action_type": ["split"],
            "ratio": [2.0],
            "amount": [None],
        },
        schema_overrides={"amount": pl.Float64},
    )
    result = apply_adjustments(daily, actions).sort("date")
    # Prior closes get factor=1/2; ex-date close unchanged.
    assert result["adj_close"].to_list() == [500_000, 505_000, 500_000]


@pytest.mark.unit
def test_cash_dividend_adjusts_prior():
    # Dividend 100 VND/share on 2024-01-04; close on 2024-01-03 = 1000.
    # Factor = (1000 - 100) / 1000 = 0.9. Prior close 1000 → 900.
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 3), date(2024, 1, 4)],
            "symbol": ["VNM", "VNM"],
            "close": [1000, 900],
        }
    )
    actions = pl.DataFrame(
        {
            "ex_date": [date(2024, 1, 4)],
            "symbol": ["VNM"],
            "action_type": ["dividend_cash"],
            "ratio": [None],
            "amount": [100.0],
        },
        schema_overrides={"ratio": pl.Float64},
    )
    result = apply_adjustments(daily, actions).sort("date")
    # adj_close[Jan 3] = 1000 * 0.9 = 900; adj_close[Jan 4] = 900 (no later actions)
    assert result["adj_close"].to_list() == [900, 900]


@pytest.mark.unit
def test_stock_dividend_10pct():
    # 10% stock dividend → ratio=0.1, factor=1/1.1 ≈ 0.909
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 3), date(2024, 1, 4)],
            "symbol": ["VNM", "VNM"],
            "close": [1000, 909],
        }
    )
    actions = pl.DataFrame(
        {
            "ex_date": [date(2024, 1, 4)],
            "symbol": ["VNM"],
            "action_type": ["dividend_stock"],
            "ratio": [0.1],
            "amount": [None],
        },
        schema_overrides={"amount": pl.Float64},
    )
    result = apply_adjustments(daily, actions).sort("date")
    # adj_close[Jan 3] = 1000 * 1/1.1 = 909 (rounded down via Int64 cast)
    assert abs(result["adj_close"][0] - 909) <= 1


@pytest.mark.unit
def test_action_factor_split():
    assert _action_factor("split", 2.0, None, None) == 0.5


@pytest.mark.unit
def test_action_factor_stock_dividend():
    assert abs(_action_factor("dividend_stock", 0.1, None, None) - 1 / 1.1) < 1e-9


@pytest.mark.unit
def test_action_factor_cash_dividend():
    assert _action_factor("dividend_cash", None, 100.0, 1000.0) == 0.9


@pytest.mark.unit
def test_action_factor_cash_dividend_no_close_prev():
    """Missing close_prev → factor=1.0 (no-op)."""
    assert _action_factor("dividend_cash", None, 100.0, None) == 1.0


@pytest.mark.unit
def test_action_factor_merger_noop():
    assert _action_factor("merger", None, None, None) == 1.0


@pytest.mark.unit
def test_action_factor_unknown_noop():
    assert _action_factor("delisting", None, None, None) == 1.0
