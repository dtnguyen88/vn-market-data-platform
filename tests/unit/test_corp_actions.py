"""Unit tests for batch.eod.corp_actions.

All tests use monkeypatched source functions or canned fixtures — no network calls.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest
from batch.eod.corp_actions import (
    _normalize_corp_actions,
    pull_corp_actions,
)
from shared.fallback import AllSourcesFailed

FIX = Path(__file__).parent.parent / "fixtures" / "vnstock"


def _fixture_to_pandas_df(name: str) -> pd.DataFrame:
    """Load synthetic vnstock-shape fixture as pandas DataFrame."""
    rows = json.loads((FIX / name).read_text())
    df = pd.DataFrame(rows)
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    for col in ("record_date", "payment_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


@pytest.mark.unit
def test_normalize_corp_actions_produces_target_schema():
    pdf = _fixture_to_pandas_df("corp-actions-vnm.json")
    df = _normalize_corp_actions(pdf, "VNM")

    assert df.shape[0] == 2
    expected_cols = {
        "ex_date",
        "symbol",
        "action_type",
        "ratio",
        "amount",
        "record_date",
        "payment_date",
    }
    assert expected_cols <= set(df.columns)
    assert df["symbol"][0] == "VNM"
    assert df["action_type"][0] == "dividend_cash"
    # ratio is None for cash dividend row
    assert df["ratio"][0] is None
    assert df["amount"][0] == pytest.approx(1500.0)


@pytest.mark.unit
def test_normalize_corp_actions_ex_date_alias():
    """Verify alternative ex_date column names are normalised."""
    pdf = pd.DataFrame(
        [
            {
                "ngay_giao_dich_khong_huong_quyen": "2026-05-15",
                "action_type": "dividend_cash",
                "amount": 1500,
            }
        ]
    )
    col = "ngay_giao_dich_khong_huong_quyen"
    pdf[col] = pd.to_datetime(pdf[col])
    df = _normalize_corp_actions(pdf, "VNM")
    assert "ex_date" in df.columns
    assert df["ex_date"][0] == date(2026, 5, 15)


@pytest.mark.unit
def test_pull_corp_actions_30_day_forward_filter():
    """Only ex_dates within [today, today+30] are returned."""
    pdf = _fixture_to_pandas_df("corp-actions-vnm.json")

    def fake_tcbs(symbol, start, end):
        df = _normalize_corp_actions(pdf, symbol)
        return df.filter((pl.col("ex_date") >= start) & (pl.col("ex_date") <= end))

    today = date(2026, 4, 27)
    with patch("batch.eod.corp_actions.pull_corp_actions_tcbs", side_effect=fake_tcbs):
        result = pull_corp_actions("VNM", today)

    # 2026-05-15 is within 30 days; 2026-08-10 is not
    assert result.shape[0] == 1
    assert result["ex_date"][0] == date(2026, 5, 15)


@pytest.mark.unit
def test_pull_corp_actions_falls_through_to_vci():
    expected = pl.DataFrame({"ex_date": [date(2026, 5, 15)], "symbol": ["VNM"]})

    def tcbs_fail(*a, **kw):
        raise RuntimeError("tcbs down")

    with (
        patch("batch.eod.corp_actions.pull_corp_actions_tcbs", side_effect=tcbs_fail),
        patch("batch.eod.corp_actions.pull_corp_actions_vci", return_value=expected),
    ):
        result = pull_corp_actions("VNM", date(2026, 4, 27))
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_corp_actions_all_fail_raises():
    def boom(*a, **kw):
        raise RuntimeError("source down")

    with (
        patch("batch.eod.corp_actions.pull_corp_actions_tcbs", side_effect=boom),
        patch("batch.eod.corp_actions.pull_corp_actions_vci", side_effect=boom),
    ):
        with pytest.raises(AllSourcesFailed):
            pull_corp_actions("VNM", date(2026, 4, 27))
