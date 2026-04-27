"""Unit tests for batch.reference tickers and futures pulls."""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest
from batch.reference.futures import _normalize_futures, pull_futures
from batch.reference.tickers import _normalize_tickers, pull_tickers
from shared.fallback import AllSourcesFailed

FIX = Path(__file__).parent.parent / "fixtures" / "vnstock"


def _load_fixture_pdf(name: str) -> pd.DataFrame:
    rows = json.loads((FIX / name).read_text())
    return pd.DataFrame(rows)


@pytest.mark.unit
def test_normalize_tickers_schema():
    pdf = _load_fixture_pdf("tickers-master.json")
    df = _normalize_tickers(pdf)
    expected_cols = {
        "symbol",
        "name",
        "exchange",
        "asset_class",
        "sector_l1",
        "sector_l2",
        "industry",
        "listed_date",
        "status",
        "lot_size",
        "tick_size",
        "foreign_room_pct",
    }
    assert set(df.columns) == expected_cols
    assert df.shape[0] == 2
    assert df["symbol"][0] == "VNM"


@pytest.mark.unit
def test_pull_tickers_first_succeeds():
    expected = pl.DataFrame({"symbol": ["X"], "name": ["X Co"]})
    with patch("batch.reference.tickers.pull_tickers_tcbs", return_value=expected):
        result = pull_tickers()
        assert result.equals(expected)


@pytest.mark.unit
def test_pull_tickers_falls_through():
    expected = pl.DataFrame({"symbol": ["Y"]})

    def boom(*a, **kw):
        raise RuntimeError("tcbs down")

    with (
        patch("batch.reference.tickers.pull_tickers_tcbs", side_effect=boom),
        patch("batch.reference.tickers.pull_tickers_vci", return_value=expected),
    ):
        assert pull_tickers().equals(expected)


@pytest.mark.unit
def test_normalize_futures_schema():
    pdf = _load_fixture_pdf("futures-master.json")
    df = _normalize_futures(pdf)
    expected_cols = {
        "symbol",
        "underlying_index",
        "expiry_date",
        "contract_size",
        "tick_size",
        "margin_pct",
    }
    assert set(df.columns) == expected_cols
    assert df.shape[0] == 2
    assert df["underlying_index"][0] == "VN30"


@pytest.mark.unit
def test_pull_futures_all_fail():
    def boom(*a, **kw):
        raise RuntimeError("down")

    with patch("batch.reference.futures.pull_futures_tcbs", side_effect=boom):
        with pytest.raises(AllSourcesFailed):
            pull_futures()
