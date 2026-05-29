"""Unit tests for curate.adjustments."""

import time
from datetime import date, timedelta

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


@pytest.mark.unit
def test_multi_symbol_multi_action_isolated():
    """3 symbols with different actions: each symbol's adj_close uses only its own factors."""
    daily = pl.DataFrame(
        {
            "date": [
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
            ],
            "symbol": ["VNM", "VNM", "VNM", "FPT", "FPT", "FPT", "HPG", "HPG", "HPG"],
            "close": [2000, 2010, 1000, 100_000, 100_500, 100_800, 30_000, 30_300, 27_300],
        }
    )
    actions = pl.DataFrame(
        {
            "ex_date": [date(2024, 1, 4), date(2024, 1, 4)],
            "symbol": ["VNM", "HPG"],
            "action_type": ["split", "dividend_stock"],
            "ratio": [2.0, 0.1],
            "amount": [None, None],
        },
        schema_overrides={"amount": pl.Float64},
    )
    result = apply_adjustments(daily, actions).sort(["symbol", "date"])
    by_sym = {
        s: result.filter(pl.col("symbol") == s)["adj_close"].to_list()
        for s in ("VNM", "FPT", "HPG")
    }
    # VNM split 2:1 — Jan 2/3 halved, Jan 4 unchanged.
    assert by_sym["VNM"] == [1000, 1005, 1000]
    # FPT — no actions, adj_close = close.
    assert by_sym["FPT"] == [100_000, 100_500, 100_800]
    # HPG stock div 10% — Jan 2/3 * (1/1.1); Jan 4 unchanged.
    assert abs(by_sym["HPG"][0] - 27_272) <= 1
    assert abs(by_sym["HPG"][1] - 27_545) <= 1
    assert by_sym["HPG"][2] == 27_300


@pytest.mark.unit
def test_perf_budget_50k_rows_300_actions():
    """Vectorized path must process 50k daily rows x 300 actions in < 5 s."""
    n_symbols = 100
    n_days = 500
    base_date = date(2022, 1, 1)
    symbols = [f"S{i:03d}" for i in range(n_symbols)]
    rows = []
    for s in symbols:
        for d in range(n_days):
            rows.append({"date": base_date + timedelta(days=d), "symbol": s, "close": 10_000 + d})
    daily = pl.DataFrame(rows)

    # 3 actions per symbol — splits at varying ex_dates → 300 corp action rows.
    act_rows = []
    for s in symbols:
        for offset in (100, 250, 400):
            act_rows.append(
                {
                    "ex_date": base_date + timedelta(days=offset),
                    "symbol": s,
                    "action_type": "split",
                    "ratio": 2.0,
                    "amount": None,
                }
            )
    actions = pl.DataFrame(act_rows, schema_overrides={"amount": pl.Float64})

    t0 = time.perf_counter()
    result = apply_adjustments(daily, actions)
    elapsed = time.perf_counter() - t0
    assert result.height == n_symbols * n_days
    assert "adj_close" in result.columns
    assert elapsed < 5.0, f"apply_adjustments took {elapsed:.2f}s, budget 5s"
