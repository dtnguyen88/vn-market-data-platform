"""Unit tests for curate.dedup."""

from datetime import UTC, datetime

import polars as pl
import pytest
from curate.dedup import dedup_polars


@pytest.mark.unit
def test_dedup_keeps_first_occurrence():
    df = pl.DataFrame(
        {
            "symbol": ["VNM", "VNM", "VIC"],
            "ts_event": [
                datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC),
                datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC),
                datetime(2026, 4, 28, 9, 0, 1, tzinfo=UTC),
            ],
            "price": [850000, 851000, 410000],
        }
    )
    result = dedup_polars(df, keys=["symbol", "ts_event"])
    assert result.height == 2
    assert result.filter(pl.col("symbol") == "VNM")["price"][0] == 850000


@pytest.mark.unit
def test_dedup_no_duplicates_returns_unchanged_height():
    df = pl.DataFrame({"symbol": ["A", "B", "C"], "ts": [1, 2, 3]})
    result = dedup_polars(df, keys=["symbol", "ts"])
    assert result.height == 3


@pytest.mark.unit
def test_dedup_three_key_tuple():
    df = pl.DataFrame(
        {
            "symbol": ["VNM"] * 3,
            "ts_event": [1, 1, 2],
            "trade_id": ["T1", "T1", "T1"],
        }
    )
    result = dedup_polars(df, keys=["symbol", "ts_event", "trade_id"])
    assert result.height == 2  # (VNM,1,T1) and (VNM,2,T1)


@pytest.mark.unit
def test_dedup_with_sort_by_changes_kept_row():
    df = pl.DataFrame(
        {
            "symbol": ["VNM", "VNM"],
            "ts_event": [1, 1],
            "price": [851000, 850000],  # second has lower price
        }
    )
    # Without sort, first occurrence (851000) wins.
    r1 = dedup_polars(df, keys=["symbol", "ts_event"])
    assert r1["price"][0] == 851000

    # With sort by price asc, lower price (850000) becomes first.
    r2 = dedup_polars(df, keys=["symbol", "ts_event"], sort_by="price")
    assert r2["price"][0] == 850000


@pytest.mark.unit
def test_dedup_lazy_frame_returns_lazy():
    df = pl.LazyFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    result = dedup_polars(df, keys=["a", "b"])
    assert isinstance(result, pl.LazyFrame)
    assert result.collect().height == 2


@pytest.mark.unit
def test_dedup_empty_frame():
    df = pl.DataFrame(
        {"symbol": [], "ts_event": []},
        schema={"symbol": pl.Utf8, "ts_event": pl.Int64},
    )
    result = dedup_polars(df, keys=["symbol", "ts_event"])
    assert result.height == 0
