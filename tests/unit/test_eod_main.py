"""Unit tests for batch.eod entrypoint helpers.

Tests cover:
- _resolve_target_date() honors TARGET_DATE env var
- _resolve_target_date() defaults to yesterday in Asia/Ho_Chi_Minh
- _load_symbols() falls back to dev sample when override_url is None
- _load_symbols() reads from GCS when override_url is provided
"""

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from batch.eod.__main__ import _load_symbols, _resolve_target_date

VN = ZoneInfo("Asia/Ho_Chi_Minh")


@pytest.mark.unit
def test_target_date_from_env(monkeypatch):
    monkeypatch.setenv("TARGET_DATE", "2025-04-15")
    assert _resolve_target_date() == date(2025, 4, 15)


@pytest.mark.unit
def test_target_date_default_yesterday_vn(monkeypatch):
    monkeypatch.delenv("TARGET_DATE", raising=False)
    result = _resolve_target_date()
    # Robust to TZ jitter at month/year boundaries — allow ±2-day window
    today_vn = datetime.now(VN).date()
    assert today_vn - timedelta(days=2) <= result <= today_vn


@pytest.mark.unit
def test_load_symbols_fallback_when_no_url():
    storage_client = MagicMock()
    syms = _load_symbols(storage_client, env="staging", override_url=None)
    assert len(syms) >= 5
    assert all(set(s.keys()) >= {"symbol", "asset_class", "exchange"} for s in syms)
    assert any(s["symbol"] == "VNM" for s in syms)
    # Storage client must not be touched when no URL provided
    storage_client.bucket.assert_not_called()


@pytest.mark.unit
def test_load_symbols_reads_url():
    storage_client = MagicMock()
    blob = MagicMock()
    blob.download_as_text.return_value = json.dumps(
        [
            {"symbol": "ABC", "asset_class": "equity", "exchange": "HOSE"},
        ]
    )
    storage_client.bucket.return_value.blob.return_value = blob
    syms = _load_symbols(
        storage_client,
        env="staging",
        override_url="gs://my-bucket/path/to/eod-symbols.json",
    )
    assert syms == [{"symbol": "ABC", "asset_class": "equity", "exchange": "HOSE"}]
    storage_client.bucket.assert_called_once_with("my-bucket")
    storage_client.bucket.return_value.blob.assert_called_once_with("path/to/eod-symbols.json")
