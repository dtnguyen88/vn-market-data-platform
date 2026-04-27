"""Unit tests for SSI WebSocket message parsers using synthetic golden fixtures.

Tests validate the parse_tick, parse_quote_l1, parse_quote_l2, parse_index
functions against hand-crafted fixtures in tests/fixtures/ssi/.

Note: QuoteL2 uses a flat schema (bid_px_1..bid_px_10, ask_px_1..ask_px_10)
rather than nested lists — tests reflect this flat structure.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from publisher.parsers import parse_index, parse_quote_l1, parse_quote_l2, parse_tick
from shared.schemas import IndexValue, MatchType, QuoteL1, QuoteL2, Tick

FIX = Path(__file__).parent.parent / "fixtures" / "ssi"
TS = datetime(2026, 4, 27, 9, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_parse_tick_returns_tick_model():
    raw = json.loads((FIX / "ticks_sample.json").read_text())[0]
    result = parse_tick(raw, ts_received=TS)
    assert isinstance(result, Tick)
    assert result.symbol == "VNM"
    assert result.price == 850000
    assert result.volume == 100


@pytest.mark.unit
def test_parse_tick_classifies_future():
    raw = json.loads((FIX / "ticks_sample.json").read_text())[3]
    result = parse_tick(raw, ts_received=TS)
    assert result.asset_class.value == "future"
    assert result.symbol == "VN30F1M"


@pytest.mark.unit
def test_parse_tick_handles_ato_match_type():
    raw = {
        "S": "VNM",
        "P": 850000,
        "V": 100,
        "T": 1714180800000,
        "MT": "ATO",
        "TID": "T1",
        "SEQ": 1,
        "EX": "HOSE",
        "SD": "B",
    }
    result = parse_tick(raw, ts_received=TS)
    assert result.match_type == MatchType.ATO


@pytest.mark.unit
def test_parse_quote_l1_computes_mid_and_spread():
    raw = json.loads((FIX / "quotes_l1_sample.json").read_text())[0]
    result = parse_quote_l1(raw, ts_received=TS)
    assert isinstance(result, QuoteL1)
    assert result.mid_price == 850000  # (849000 + 851000) // 2
    assert result.spread_bps is not None and result.spread_bps > 0


@pytest.mark.unit
def test_parse_quote_l1_no_mid_when_bid_zero():
    # FPT entry index 4 has BP=0 — one side missing, so mid/spread must be None
    raw = json.loads((FIX / "quotes_l1_sample.json").read_text())[4]
    result = parse_quote_l1(raw, ts_received=TS)
    assert result.mid_price is None
    assert result.spread_bps is None


@pytest.mark.unit
def test_parse_quote_l2_full_book():
    raw = json.loads((FIX / "quotes_l2_sample.json").read_text())[0]
    result = parse_quote_l2(raw, ts_received=TS)
    assert isinstance(result, QuoteL2)
    assert result.bid_px_1 == 849000
    assert result.bid_px_10 == 840000
    assert result.ask_px_1 == 851000
    assert result.ask_px_10 == 860000


@pytest.mark.unit
def test_parse_quote_l2_partial_book():
    # VIC entry index 1: 4 bid levels, 3 ask levels — rest must be None
    raw = json.loads((FIX / "quotes_l2_sample.json").read_text())[1]
    result = parse_quote_l2(raw, ts_received=TS)
    assert result.bid_px_1 == 409000
    assert result.bid_px_4 == 406000
    assert result.bid_px_5 is None  # only 4 bid levels filled
    assert result.ask_px_3 == 413000
    assert result.ask_px_4 is None  # only 3 ask levels filled


@pytest.mark.unit
def test_parse_index_includes_breadth_counts():
    raw = json.loads((FIX / "indices_sample.json").read_text())[0]
    result = parse_index(raw, ts_received=TS)
    assert isinstance(result, IndexValue)
    assert result.index_code == "VNINDEX"
    assert result.advance_count == 220
    assert result.value == 1234.56
