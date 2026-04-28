"""Unit tests for curate.derived_columns."""

import polars as pl
import pytest
from curate.derived_columns import add_l1_derived


@pytest.mark.unit
def test_normal_book():
    df = pl.DataFrame({"bid_price": [100], "ask_price": [102]})
    result = add_l1_derived(df)
    assert result["mid_price"][0] == 101  # (100+102)//2
    assert result["spread_bps"][0] == round(10000 * 2 / 101)  # = 198


@pytest.mark.unit
def test_zero_bid():
    df = pl.DataFrame({"bid_price": [0], "ask_price": [102]})
    result = add_l1_derived(df)
    assert result["mid_price"][0] is None
    assert result["spread_bps"][0] is None


@pytest.mark.unit
def test_zero_ask():
    df = pl.DataFrame({"bid_price": [100], "ask_price": [0]})
    result = add_l1_derived(df)
    assert result["mid_price"][0] is None
    assert result["spread_bps"][0] is None


@pytest.mark.unit
def test_locked_book_zero_spread():
    df = pl.DataFrame({"bid_price": [100], "ask_price": [100]})
    result = add_l1_derived(df)
    assert result["mid_price"][0] == 100
    assert result["spread_bps"][0] == 0


@pytest.mark.unit
def test_crossed_book_negative_spread():
    df = pl.DataFrame({"bid_price": [102], "ask_price": [100]})
    result = add_l1_derived(df)
    assert result["mid_price"][0] == 101
    assert result["spread_bps"][0] < 0


@pytest.mark.unit
def test_lazy_frame():
    lf = pl.LazyFrame({"bid_price": [100, 0, 200], "ask_price": [102, 105, 0]})
    result = add_l1_derived(lf).collect()
    assert result.shape[0] == 3
    assert result["mid_price"].to_list() == [101, None, None]
