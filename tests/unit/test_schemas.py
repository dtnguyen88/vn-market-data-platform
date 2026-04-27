"""Unit tests for shared.schemas — Pydantic v2 stream models.

Tests cover:
  - Valid construction for all 4 model types
  - Rejection of invalid types and missing required fields
  - Computed fields (mid_price, spread_bps) on QuoteL1
  - Round-trip JSON serialisation/deserialisation
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from shared.schemas import (
    AssetClass,
    Exchange,
    IndexValue,
    MatchType,
    QuoteL1,
    QuoteL2,
    Side,
    Tick,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VN_TZ_OFFSET = 7 * 3600  # UTC+7 in seconds
_TS_EVENT = datetime(2026, 4, 27, 9, 15, 0, tzinfo=UTC)
_TS_RECEIVED = datetime(2026, 4, 27, 2, 15, 0, tzinfo=UTC)

_COMMON = {
    "ts_event": _TS_EVENT,
    "ts_received": _TS_RECEIVED,
    "symbol": "VNM",
    "asset_class": AssetClass.EQUITY,
    "exchange": Exchange.HOSE,
}


def _make_tick(**overrides) -> dict:
    base = {
        **_COMMON,
        "price": 45_000,
        "volume": 1_000,
        "match_type": MatchType.CONTINUOUS,
        "side": Side.BUY,
        "trade_id": "TX-0001",
        "seq": 42,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tick tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tick_valid_construction():
    t = Tick(**_make_tick())
    assert t.symbol == "VNM"
    assert t.price == 45_000
    assert t.volume == 1_000
    assert t.match_type == MatchType.CONTINUOUS
    assert t.side == Side.BUY
    assert t.trade_id == "TX-0001"
    assert t.seq == 42
    assert t.exchange == Exchange.HOSE
    assert t.asset_class == AssetClass.EQUITY
    # schema_version is a ClassVar — not a Pydantic field
    assert Tick.schema_version == "1"
    assert "schema_version" not in Tick.model_fields


@pytest.mark.unit
def test_tick_rejects_negative_price():
    with pytest.raises(ValidationError):
        Tick(**_make_tick(price=-1))


@pytest.mark.unit
def test_tick_rejects_negative_volume():
    with pytest.raises(ValidationError):
        Tick(**_make_tick(volume=-100))


@pytest.mark.unit
def test_tick_rejects_missing_required_field():
    data = _make_tick()
    del data["trade_id"]
    with pytest.raises(ValidationError):
        Tick(**data)


@pytest.mark.unit
def test_tick_rejects_wrong_price_type():
    with pytest.raises(ValidationError):
        Tick(**_make_tick(price="not-a-number"))


@pytest.mark.unit
def test_tick_is_frozen():
    t = Tick(**_make_tick())
    with pytest.raises(ValidationError):
        t.price = 99_999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# QuoteL1 tests
# ---------------------------------------------------------------------------


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
    """bid=100, ask=102 → mid=101, spread_bps=round(10000*2/101)=198."""
    q = QuoteL1(**_make_quote_l1())
    assert q.mid_price == 101
    assert q.spread_bps == round(10000 * 2 / 101)  # 198


@pytest.mark.unit
def test_quote_l1_no_mid_when_bid_zero():
    """bid=0 → neither side is truthy, mid and spread must be None."""
    q = QuoteL1(**_make_quote_l1(bid_price=0))
    assert q.mid_price is None
    assert q.spread_bps is None


@pytest.mark.unit
def test_quote_l1_no_mid_when_ask_zero():
    q = QuoteL1(**_make_quote_l1(ask_price=0))
    assert q.mid_price is None
    assert q.spread_bps is None


@pytest.mark.unit
def test_quote_l1_valid_construction():
    q = QuoteL1(**_make_quote_l1())
    assert q.bid_price == 100
    assert q.ask_price == 102
    assert QuoteL1.schema_version == "1"
    assert "schema_version" not in QuoteL1.model_fields


@pytest.mark.unit
def test_quote_l1_rejects_negative_bid():
    with pytest.raises(ValidationError):
        QuoteL1(**_make_quote_l1(bid_price=-1))


@pytest.mark.unit
def test_quote_l1_rejects_missing_field():
    data = _make_quote_l1()
    del data["ask_size"]
    with pytest.raises(ValidationError):
        QuoteL1(**data)


# ---------------------------------------------------------------------------
# QuoteL2 tests
# ---------------------------------------------------------------------------


def _make_quote_l2(**overrides) -> dict:
    base = {**_COMMON}
    base.update(overrides)
    return base


@pytest.mark.unit
def test_quote_l2_partial_book():
    """Only first 3 levels populated; levels 4-10 are None."""
    q = QuoteL2(
        **_make_quote_l2(
            bid_px_1=100,
            bid_sz_1=500,
            bid_n_1=3,
            bid_px_2=99,
            bid_sz_2=200,
            bid_n_2=2,
            bid_px_3=98,
            bid_sz_3=100,
            bid_n_3=1,
            ask_px_1=101,
            ask_sz_1=400,
            ask_n_1=2,
            ask_px_2=102,
            ask_sz_2=300,
            ask_n_2=3,
            ask_px_3=103,
            ask_sz_3=150,
            ask_n_3=1,
        )
    )
    assert q.bid_px_1 == 100
    assert q.bid_px_3 == 98
    assert q.bid_px_4 is None
    assert q.ask_px_3 == 103
    assert q.ask_px_4 is None
    assert q.bid_n_10 is None
    assert QuoteL2.schema_version == "1"


@pytest.mark.unit
def test_quote_l2_empty_book():
    """All optional — empty book must be accepted."""
    q = QuoteL2(**_make_quote_l2())
    assert q.bid_px_1 is None
    assert q.ask_px_10 is None


@pytest.mark.unit
def test_quote_l2_rejects_negative_price():
    with pytest.raises(ValidationError):
        QuoteL2(**_make_quote_l2(bid_px_1=-5))


@pytest.mark.unit
def test_quote_l2_rejects_missing_required_field():
    data = _make_quote_l2()
    del data["symbol"]
    with pytest.raises(ValidationError):
        QuoteL2(**data)


# ---------------------------------------------------------------------------
# IndexValue tests
# ---------------------------------------------------------------------------


def _make_index_value(**overrides) -> dict:
    base = {
        "ts_event": _TS_EVENT,
        "ts_received": _TS_RECEIVED,
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
    iv = IndexValue(**_make_index_value())
    assert iv.index_code == "VNINDEX"
    assert iv.value == pytest.approx(1_250.75)
    assert iv.change == pytest.approx(-3.25)
    assert iv.change_pct == pytest.approx(-0.26)
    assert iv.advance_count == 180
    assert iv.decline_count == 120
    assert iv.unchanged_count == 50
    assert IndexValue.schema_version == "1"
    assert "schema_version" not in IndexValue.model_fields


@pytest.mark.unit
def test_index_value_allows_negative_change():
    """change and change_pct have no ge constraint — negative values are valid."""
    iv = IndexValue(**_make_index_value(change=-50.0, change_pct=-4.0))
    assert iv.change == pytest.approx(-50.0)


@pytest.mark.unit
def test_index_value_rejects_negative_volume():
    with pytest.raises(ValidationError):
        IndexValue(**_make_index_value(total_volume=-1))


@pytest.mark.unit
def test_index_value_rejects_missing_field():
    data = _make_index_value()
    del data["index_code"]
    with pytest.raises(ValidationError):
        IndexValue(**data)


# ---------------------------------------------------------------------------
# Round-trip JSON serialisation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_round_trip_json_tick():
    original = Tick(**_make_tick())
    json_str = original.model_dump_json()
    restored = Tick.model_validate_json(json_str)
    assert restored == original
    # Datetime preserved with timezone info
    assert restored.ts_event.tzinfo is not None
    assert restored.ts_received.tzinfo is not None


@pytest.mark.unit
def test_round_trip_json_quote_l1():
    original = QuoteL1(**_make_quote_l1())
    restored = QuoteL1.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.mid_price == original.mid_price
    assert restored.spread_bps == original.spread_bps


@pytest.mark.unit
def test_round_trip_json_quote_l2():
    original = QuoteL2(**_make_quote_l2(bid_px_1=100, bid_sz_1=500, bid_n_1=3))
    restored = QuoteL2.model_validate_json(original.model_dump_json())
    assert restored == original


@pytest.mark.unit
def test_round_trip_json_index_value():
    original = IndexValue(**_make_index_value())
    restored = IndexValue.model_validate_json(original.model_dump_json())
    assert restored == original


@pytest.mark.unit
def test_json_serialises_datetime_as_iso8601():
    """Datetime fields must appear as ISO 8601 strings in JSON output."""
    import json

    t = Tick(**_make_tick())
    payload = json.loads(t.model_dump_json())
    # ISO 8601 string — must be parseable and contain timezone marker
    ts = payload["ts_event"]
    assert isinstance(ts, str)
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
