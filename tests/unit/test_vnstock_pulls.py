"""Unit tests for batch.eod.vnstock_pulls.

All tests use monkeypatched source functions or canned fixtures — no network calls.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest
from batch.eod.vnstock_pulls import (
    _normalize,
    pull_daily,
)
from shared.fallback import AllSourcesFailed

FIX = Path(__file__).parent.parent / "fixtures" / "vnstock"


def _fixture_to_pandas_df(name: str):
    """Load synthetic vnstock-shape fixture as pandas DataFrame."""
    import pandas as pd

    rows = json.loads((FIX / name).read_text())
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    return df


@pytest.mark.unit
def test_normalize_produces_target_schema():
    pdf = _fixture_to_pandas_df("daily-vnm.json")
    df = _normalize(pdf, "VNM", "equity", "HOSE")

    assert df.shape[0] == 5
    expected_cols = {
        "date",
        "symbol",
        "asset_class",
        "exchange",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "value",
        "foreign_buy_vol",
        "foreign_sell_vol",
    }
    assert expected_cols <= set(df.columns)
    # 1/10 VND scaling: vnstock 85500 → 855000
    assert df["close"][0] == 855000
    assert df["symbol"][0] == "VNM"
    # value = close * volume
    assert df["value"][0] == 855000 * 100000


@pytest.mark.unit
def test_pull_daily_first_source_succeeds():
    expected = pl.DataFrame(
        {
            "date": [date(2024, 1, 2)],
            "symbol": ["VNM"],
            "asset_class": ["equity"],
            "exchange": ["HOSE"],
            "open": [850000],
            "high": [860000],
            "low": [845000],
            "close": [855000],
            "volume": [100000],
            "value": [85_500_000_000],
            "foreign_buy_vol": pl.Series([None], dtype=pl.Int64),
            "foreign_sell_vol": pl.Series([None], dtype=pl.Int64),
        }
    )
    with patch("batch.eod.vnstock_pulls.pull_daily_tcbs", return_value=expected):
        result = pull_daily("VNM", date(2024, 1, 2), date(2024, 1, 8))
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_daily_falls_through_to_vci():
    expected = pl.DataFrame({"date": [date(2024, 1, 2)], "symbol": ["VNM"]})

    def tcbs_fail(*a, **kw):
        raise RuntimeError("tcbs down")

    with (
        patch("batch.eod.vnstock_pulls.pull_daily_tcbs", side_effect=tcbs_fail),
        patch("batch.eod.vnstock_pulls.pull_daily_vci", return_value=expected),
    ):
        result = pull_daily("VNM", date(2024, 1, 2), date(2024, 1, 8))
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_daily_all_fail_raises():
    def boom(*a, **kw):
        raise RuntimeError("source down")

    with (
        patch("batch.eod.vnstock_pulls.pull_daily_tcbs", side_effect=boom),
        patch("batch.eod.vnstock_pulls.pull_daily_vci", side_effect=boom),
        patch("batch.eod.vnstock_pulls.pull_daily_ssi", side_effect=boom),
    ):
        with pytest.raises(AllSourcesFailed):
            pull_daily("VNM", date(2024, 1, 2), date(2024, 1, 8))
