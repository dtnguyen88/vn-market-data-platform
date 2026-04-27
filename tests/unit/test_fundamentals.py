"""Unit tests for batch.eod.fundamentals.

All tests use monkeypatched source functions or canned fixtures — no network calls.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest
from batch.eod.fundamentals import (
    _normalize_fundamentals,
    is_quarterly_report_date,
    pull_fundamentals,
)
from shared.fallback import AllSourcesFailed

FIX = Path(__file__).parent.parent / "fixtures" / "vnstock"


def _fixture_to_pandas_df(name: str) -> pd.DataFrame:
    """Load synthetic vnstock-shape fixture as pandas DataFrame."""
    rows = json.loads((FIX / name).read_text())
    df = pd.DataFrame(rows)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


@pytest.mark.unit
def test_normalize_fundamentals_produces_target_schema():
    pdf = _fixture_to_pandas_df("fundamentals-vnm.json")
    df = _normalize_fundamentals(pdf, "VNM")

    assert df.shape[0] == 2
    expected_cols = {
        "as_of_date",
        "symbol",
        "period",
        "pe",
        "pb",
        "eps",
        "bvps",
        "roe",
        "roa",
        "debt_to_equity",
        "market_cap",
        "revenue",
        "net_income",
        "total_assets",
        "total_equity",
    }
    assert expected_cols <= set(df.columns)
    assert df["symbol"][0] == "VNM"
    # period derived from year + quarter columns: "2024-Q3" for first row
    assert df["period"][0] == "2024-Q3"
    assert df["pe"][0] == pytest.approx(15.2)
    assert df["market_cap"][0] == 184_000_000_000_000


@pytest.mark.unit
def test_normalize_fundamentals_missing_cols_filled_with_none():
    """Columns absent from the source frame are added as None with correct dtype."""
    pdf = pd.DataFrame([{"as_of_date": "2024-09-30", "pe": 15.2}])
    pdf["as_of_date"] = pd.to_datetime(pdf["as_of_date"])
    df = _normalize_fundamentals(pdf, "VNM")

    # revenue should exist as Int64 None
    assert "revenue" in df.columns
    assert df.schema["revenue"] == pl.Int64
    assert df["revenue"][0] is None


@pytest.mark.unit
def test_pull_fundamentals_first_source_succeeds():
    expected = pl.DataFrame({"as_of_date": [date(2024, 9, 30)], "symbol": ["VNM"]})
    with patch("batch.eod.fundamentals.pull_fundamentals_tcbs", return_value=expected):
        result = pull_fundamentals("VNM")
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_fundamentals_falls_through_to_vci():
    expected = pl.DataFrame({"as_of_date": [date(2024, 9, 30)], "symbol": ["VNM"]})

    def tcbs_fail(*a, **kw):
        raise RuntimeError("tcbs down")

    with (
        patch("batch.eod.fundamentals.pull_fundamentals_tcbs", side_effect=tcbs_fail),
        patch("batch.eod.fundamentals.pull_fundamentals_vci", return_value=expected),
    ):
        result = pull_fundamentals("VNM")
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_fundamentals_all_fail_raises():
    def boom(*a, **kw):
        raise RuntimeError("source down")

    with (
        patch("batch.eod.fundamentals.pull_fundamentals_tcbs", side_effect=boom),
        patch("batch.eod.fundamentals.pull_fundamentals_vci", side_effect=boom),
    ):
        with pytest.raises(AllSourcesFailed):
            pull_fundamentals("VNM")


@pytest.mark.unit
@pytest.mark.parametrize(
    "d, expected",
    [
        (date(2024, 4, 30), True),  # exact Q1 deadline
        (date(2024, 4, 27), True),  # 3 days before Q1 deadline
        (date(2024, 7, 30), True),  # exact Q2 deadline
        (date(2024, 10, 30), True),  # exact Q3 deadline
        (date(2025, 1, 30), True),  # exact Q4 deadline (next year)
        (date(2024, 6, 15), False),  # mid-June — not near any deadline
        (date(2024, 4, 24), False),  # 6 days before Q1 — outside window
    ],
)
def test_is_quarterly_report_date(d: date, expected: bool):
    assert is_quarterly_report_date(d) is expected
