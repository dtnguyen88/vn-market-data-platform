"""Unit tests for writers.schema_validator — Pydantic validate-or-None."""

import pytest
from shared.schemas import IndexValue
from writers.schema_validator import validate


@pytest.mark.unit
def test_validate_valid_returns_model():
    body = (
        b'{"ts_event":"2026-04-27T09:00:00Z","ts_received":"2026-04-27T09:00:01Z",'
        b'"index_code":"VNINDEX","exchange":"HOSE","value":1234.56,"change":12.34,'
        b'"change_pct":1.01,"total_volume":50000000,"total_value":1500000000000,'
        b'"advance_count":220,"decline_count":180,"unchanged_count":50}'
    )
    result = validate(body, IndexValue)
    assert result is not None
    assert result.index_code == "VNINDEX"


@pytest.mark.unit
def test_validate_invalid_returns_none():
    body = b'{"ts_event":"not-a-date"}'
    assert validate(body, IndexValue) is None
