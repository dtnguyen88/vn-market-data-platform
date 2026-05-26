"""Unit tests for shared.schemas — Pydantic v2 stream models (SSI v3 shapes).

Tick is now a 1-second snapshot (open/high/low/avg + last_*); QuoteL2 dropped
the bid_n_*/ask_n_* fields (SSI v3 doesn't send order count per level).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from shared.schemas import (
    AssetClass,
    Exchange,
    ForeignRoomSnapshot,
    IndexValue,
    MatchType,
    OddLotSnapshot,
    PutThrough,
    QuoteL1,
    QuoteL2,
    Side,
    Tick,
)

_TS_EVENT = datetime(2026, 5, 26, 10, 15, 0, tzinfo=UTC)
_TS_RECV = datetime(2026, 5, 26, 3, 15, 0, tzinfo=UTC)

_COMMON = {
    "ts_event": _TS_EVENT,
    "ts_received": _TS_RECV,
    "symbol": "VNM",
    "asset_class": AssetClass.EQUITY,
    "exchange": Exchange.HOSE,
}


def _make_tick(**overrides) -> dict:
    base = {
        **_COMMON,
        "open": 59100,
        "high": 59400,
        "low": 59000,
        "avg_price": 59178.38,
        "total_volume": 1_305_000,
        "last_price": 59200,
        "last_qty": 500,
        "last_side": Side.BUY,
        "match_type": MatchType.CONTINUOUS,
        "trade_id": "abc1234567890def",
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_tick_valid_construction():
    t = Tick(**_make_tick())
    assert t.symbol == "VNM"
    assert t.open == 59100
    assert t.high == 59400
    assert t.avg_price == pytest.approx(59178.38)
    assert t.total_volume == 1_305_000
    assert t.last_price == 59200
    assert t.last_side == Side.BUY
    assert t.match_type == MatchType.CONTINUOUS
    assert Tick.schema_version == "2"
    assert "schema_version" not in Tick.model_fields


@pytest.mark.unit
def test_tick_allows_zero_last_when_no_match():
    """Most wire events have last_qty=0 (no match in 1s window) — must be valid."""
    t = Tick(**_make_tick(last_price=0, last_qty=0, last_side=Side.UNKNOWN, trade_id=None))
    assert t.last_qty == 0
    assert t.trade_id is None


@pytest.mark.unit
def test_tick_rejects_negative_volume():
    with pytest.raises(ValidationError):
        Tick(**_make_tick(total_volume=-1))


@pytest.mark.unit
def test_tick_is_frozen():
    t = Tick(**_make_tick())
    with pytest.raises(ValidationError):
        t.last_price = 99_999  # type: ignore[misc]


def _make_quote_l1(**overrides) -> dict:
    base = {
        **_COMMON,
        "bid_price": 100,
        "bid_size": 500,
        "ask_price": 102,
        "ask_size": 300,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_quote_l1_computes_mid_and_spread():
    q = QuoteL1(**_make_quote_l1())
    assert q.mid_price == 101
    assert q.spread_bps == round(10000 * 2 / 101)


@pytest.mark.unit
def test_quote_l1_no_mid_when_bid_zero():
    q = QuoteL1(**_make_quote_l1(bid_price=0))
    assert q.mid_price is None
    assert q.spread_bps is None


@pytest.mark.unit
def test_quote_l1_rejects_missing_field():
    data = _make_quote_l1()
    del data["ask_size"]
    with pytest.raises(ValidationError):
        QuoteL1(**data)


@pytest.mark.unit
def test_quote_l2_partial_book():
    q = QuoteL2(
        **_COMMON,
        bid_px_1=100,
        bid_sz_1=500,
        bid_px_2=99,
        bid_sz_2=200,
        bid_px_3=98,
        bid_sz_3=100,
        ask_px_1=101,
        ask_sz_1=400,
        ask_px_2=102,
        ask_sz_2=300,
        ask_px_3=103,
        ask_sz_3=150,
    )
    assert q.bid_px_1 == 100
    assert q.bid_px_4 is None
    assert q.ask_px_10 is None
    assert QuoteL2.schema_version == "2"


@pytest.mark.unit
def test_quote_l2_empty_book():
    q = QuoteL2(**_COMMON)
    assert q.bid_px_1 is None and q.ask_px_10 is None


@pytest.mark.unit
def test_quote_l2_rejects_negative_price():
    with pytest.raises(ValidationError):
        QuoteL2(**_COMMON, bid_px_1=-5)


@pytest.mark.unit
def test_quote_l2_no_order_count_fields():
    """SSI v3 doesn't expose order count per level — schema must not have these."""
    assert "bid_n_1" not in QuoteL2.model_fields
    assert "ask_n_10" not in QuoteL2.model_fields


def _make_iv(**overrides) -> dict:
    base = {
        "ts_event": _TS_EVENT,
        "ts_received": _TS_RECV,
        "index_code": "VNINDEX",
        "exchange": Exchange.HOSE,
        "value": 1_250.75,
        "change": -3.25,
        "change_pct": -0.26,
        "total_volume": 150_000_000,
        "total_value": 3_500_000_000_000,
        "advance_count": 180,
        "decline_count": 120,
        "unchanged_count": 50,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_index_value_construction():
    iv = IndexValue(**_make_iv())
    assert iv.index_code == "VNINDEX"
    assert iv.value == pytest.approx(1_250.75)


@pytest.mark.unit
def test_index_value_allows_negative_change():
    iv = IndexValue(**_make_iv(change=-50.0, change_pct=-4.0))
    assert iv.change == pytest.approx(-50.0)


@pytest.mark.unit
def test_foreign_room_construction():
    r = ForeignRoomSnapshot(
        **_COMMON,
        total_room=100_000_000,
        current_room=50_000_000,
        buy_qty=100,
        buy_value=5_000_000,
        sell_qty=50,
        sell_value=2_500_000,
    )
    assert r.total_room == 100_000_000
    assert r.current_room == 50_000_000


@pytest.mark.unit
def test_put_through_construction():
    p = PutThrough(**_COMMON, price=24_150, qty=10_000, total_qty=50_000, total_value=1_207_500_000)
    assert p.price == 24_150
    assert p.total_value == 1_207_500_000


@pytest.mark.unit
def test_odd_lot_construction():
    o = OddLotSnapshot(
        **_COMMON,
        last_price=24_150,
        last_qty=37,
        bid_px_1=24_100,
        bid_sz_1=50,
    )
    assert o.last_qty == 37
    assert o.bid_px_2 is None


@pytest.mark.unit
def test_round_trip_json_tick():
    original = Tick(**_make_tick())
    restored = Tick.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.ts_event.tzinfo is not None


@pytest.mark.unit
def test_round_trip_json_quote_l2():
    original = QuoteL2(**_COMMON, bid_px_1=100, bid_sz_1=500)
    restored = QuoteL2.model_validate_json(original.model_dump_json())
    assert restored == original
