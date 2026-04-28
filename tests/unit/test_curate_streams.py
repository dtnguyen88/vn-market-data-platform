"""Unit tests for curate.streams — local files only, no GCS required."""

from datetime import UTC, date, datetime

import polars as pl
import pytest
from curate.streams.corp_actions import curate_corp_actions
from curate.streams.daily_ohlcv import curate_daily_ohlcv
from curate.streams.fundamentals import curate_fundamentals
from curate.streams.indices import curate_indices
from curate.streams.quotes_l1 import curate_quotes_l1
from curate.streams.quotes_l2 import curate_quotes_l2
from curate.streams.ticks import curate_ticks


def _write(tmp_path, name: str, df: pl.DataFrame) -> str:
    p = tmp_path / name
    df.write_parquet(p)
    return str(p)


@pytest.mark.unit
def test_curate_ticks_dedups(tmp_path):
    df = pl.DataFrame(
        {
            "ts_event": [datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC)] * 3,
            "symbol": ["VNM"] * 3,
            "trade_id": ["T1", "T1", "T2"],
            "price": [100, 101, 200],
        }
    )
    raw = _write(tmp_path, "raw.parquet", df)
    out = str(tmp_path / "out.parquet")
    metrics = curate_ticks(raw, out)
    assert metrics["rows_in"] == 3
    assert metrics["rows_out"] == 2  # one dup of (VNM, ts, T1)


@pytest.mark.unit
def test_curate_quotes_l1_adds_derived(tmp_path):
    df = pl.DataFrame(
        {
            "ts_event": [datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC)],
            "symbol": ["VNM"],
            "bid_price": [849000],
            "ask_price": [851000],
        }
    )
    raw = _write(tmp_path, "raw.parquet", df)
    out = str(tmp_path / "out.parquet")
    curate_quotes_l1(raw, out)
    res = pl.read_parquet(out)
    assert "mid_price" in res.columns
    assert "spread_bps" in res.columns
    assert res["mid_price"][0] == 850000


@pytest.mark.unit
def test_curate_quotes_l2_dedups(tmp_path):
    df = pl.DataFrame(
        {
            "ts_event": [datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC)] * 2,
            "symbol": ["VNM"] * 2,
            "bid_px_1": [100, 101],
        }
    )
    raw = _write(tmp_path, "raw.parquet", df)
    out = str(tmp_path / "out.parquet")
    metrics = curate_quotes_l2(raw, out)
    assert metrics["rows_out"] == 1


@pytest.mark.unit
def test_curate_indices_dedups(tmp_path):
    df = pl.DataFrame(
        {
            "ts_event": [datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC)] * 2,
            "index_code": ["VNINDEX"] * 2,
            "value": [1234.0, 1235.0],
        }
    )
    raw = _write(tmp_path, "raw.parquet", df)
    out = str(tmp_path / "out.parquet")
    metrics = curate_indices(raw, out)
    assert metrics["rows_out"] == 1


@pytest.mark.unit
def test_curate_daily_ohlcv_no_corp_actions(tmp_path):
    daily = pl.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 3)],
            "symbol": ["VNM", "VNM"],
            "close": [850000, 855000],
        }
    )
    raw = _write(tmp_path, "daily.parquet", daily)
    # Empty corp_actions with correct schema
    ca = pl.DataFrame(
        schema={
            "ex_date": pl.Date,
            "symbol": pl.Utf8,
            "action_type": pl.Utf8,
            "ratio": pl.Float64,
            "amount": pl.Float64,
        }
    )
    ca_path = _write(tmp_path, "ca.parquet", ca)
    out = str(tmp_path / "out.parquet")
    curate_daily_ohlcv(raw, ca_path, out)
    res = pl.read_parquet(out)
    assert "adj_close" in res.columns
    assert res["adj_close"].to_list() == [850000, 855000]


@pytest.mark.unit
def test_curate_fundamentals(tmp_path):
    df = pl.DataFrame(
        {
            "as_of_date": [date(2024, 9, 30)] * 2,
            "symbol": ["VNM"] * 2,
            "period": ["Q3-2024", "Q3-2024"],  # duplicate
            "pe": [15.2, 15.3],
        }
    )
    raw = _write(tmp_path, "f.parquet", df)
    out = str(tmp_path / "out.parquet")
    metrics = curate_fundamentals(raw, out)
    assert metrics["rows_out"] == 1


@pytest.mark.unit
def test_curate_corp_actions(tmp_path):
    df = pl.DataFrame(
        {
            "ex_date": [date(2024, 1, 4)] * 2,
            "symbol": ["VNM"] * 2,
            "action_type": ["dividend_cash"] * 2,
            "ratio": [None, None],
            "amount": [100.0, 100.0],
        },
        schema_overrides={"ratio": pl.Float64},
    )
    raw = _write(tmp_path, "ca.parquet", df)
    out = str(tmp_path / "out.parquet")
    metrics = curate_corp_actions(raw, out)
    assert metrics["rows_out"] == 1
