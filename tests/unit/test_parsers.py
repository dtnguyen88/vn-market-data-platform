"""Unit tests for SSI v3 wire-dict parsers — fixtures are real captured frames.

Fixtures in tests/fixtures/ssi-v3/ were captured from a live SSI WebSocket
on 2026-05-26 during VN afternoon session via scripts/ssi-fc-v3-probe.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from publisher.parsers import (
    parse_foreign_room,
    parse_odd_lot,
    parse_put_through,
    parse_quote_l1,
    parse_quote_l2,
    parse_tick,
)
from shared.schemas import (
    AssetClass,
    Exchange,
    ForeignRoomSnapshot,
    MatchType,
    OddLotSnapshot,
    PutThrough,
    QuoteL1,
    QuoteL2,
    Side,
    Tick,
)

FIX = Path(__file__).parent.parent / "fixtures" / "ssi-v3"
TS = datetime(2026, 5, 26, 7, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_parse_tick_from_live_snapshot():
    """trade-snapshot-zero fixture: SSI sent a real frame with last_qty=0 (no
    match in window). Tick must still parse, with session OHL + avg + cum-vol."""
    frame = json.loads((FIX / "trade-snapshot-zero.json").read_text())
    t = parse_tick(frame["data"], TS)
    assert isinstance(t, Tick)
    assert t.symbol == "SSI"
    assert t.open == 27_400
    assert t.high == 28_100
    assert t.low == 27_400
    assert t.avg_price == pytest.approx(27_850.61)
    assert t.total_volume == 18_195_900
    # No match in window
    assert t.last_price == 0
    assert t.last_qty == 0
    assert t.last_side == Side.UNKNOWN
    assert t.trade_id is None
    # Session-time inference (14:42:43 ICT is in ATC window 14:30-14:45)
    assert t.match_type == MatchType.ATC


@pytest.mark.unit
def test_parse_tick_with_match_synthesizes_trade_id():
    data = {
        "s": "VNM",
        "t": "2026/05/26 10:30:15",
        "p": "59200",
        "q": "500",
        "si": "B",
        "a": "59178.38",
        "o": "59100",
        "h": "59400",
        "l": "59000",
        "v": "1305000",
    }
    t = parse_tick(data, TS)
    assert t.last_price == 59_200
    assert t.last_qty == 500
    assert t.last_side == Side.BUY
    assert t.match_type == MatchType.CONTINUOUS  # 10:30 is mid-session
    assert t.trade_id is not None and len(t.trade_id) == 16


@pytest.mark.unit
def test_parse_tick_classifies_future():
    data = {
        "s": "VN30F2606",
        "t": "2026/05/26 10:00:00",
        "p": "0",
        "q": "0",
        "si": "",
        "a": "0",
        "o": "0",
        "h": "0",
        "l": "0",
        "v": "0",
    }
    t = parse_tick(data, TS)
    assert t.asset_class == AssetClass.FUTURE
    assert t.exchange == Exchange.HNX_DERIV


@pytest.mark.unit
def test_parse_quote_l2_from_live_capture():
    frame = json.loads((FIX / "quote-l2.json").read_text())
    q = parse_quote_l2(frame["data"], TS)
    assert isinstance(q, QuoteL2)
    assert q.symbol == "SSI"
    assert q.bid_px_1 == 27_950
    assert q.bid_sz_1 == 170_100
    assert q.bid_px_3 == 27_850
    assert q.bid_px_4 is None  # SSI padded with ["0","0"]
    assert q.ask_px_1 == 28_000
    assert q.ask_sz_3 == 890_900
    assert q.ask_px_10 is None


@pytest.mark.unit
def test_parse_quote_l1_derives_from_l2_frame():
    frame = json.loads((FIX / "quote-l2.json").read_text())
    q = parse_quote_l1(frame["data"], TS)
    assert isinstance(q, QuoteL1)
    assert q.bid_price == 27_950
    assert q.ask_price == 28_000
    assert q.mid_price == 27_975
    # spread = round(10000 * 50 / 27975) = 18 bps
    assert q.spread_bps == 18


@pytest.mark.unit
def test_parse_foreign_room():
    data = {
        "s": "VNM",
        "t": "2026/05/26 10:00:00",
        "tr": "100000000",
        "cr": "49000000",
        "bq": "1000",
        "bv": "59100000",
        "sq": "500",
        "sv": "29550000",
    }
    r = parse_foreign_room(data, TS)
    assert isinstance(r, ForeignRoomSnapshot)
    assert r.total_room == 100_000_000
    assert r.buy_value == 59_100_000


@pytest.mark.unit
def test_parse_put_through():
    data = {
        "s": "VNM",
        "t": "2026/05/26 10:00:00",
        "p": "59000",
        "q": "10000",
        "tq": "50000",
        "tv": "2950000000",
    }
    p = parse_put_through(data, TS)
    assert isinstance(p, PutThrough)
    assert p.price == 59_000
    assert p.total_value == 2_950_000_000


@pytest.mark.unit
def test_parse_odd_lot():
    data = {
        "s": "VNM",
        "t": "2026/05/26 10:00:00",
        "p": "59100",
        "q": "37",
        "bids": [["59000", "50"], ["58900", "20"]],
        "asks": [["59200", "30"]],
    }
    o = parse_odd_lot(data, TS)
    assert isinstance(o, OddLotSnapshot)
    assert o.last_price == 59_100
    assert o.last_qty == 37
    assert o.bid_px_1 == 59_000
    assert o.bid_px_2 == 58_900
    assert o.bid_px_3 is None
    assert o.ask_px_1 == 59_200
