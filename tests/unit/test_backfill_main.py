"""Unit tests for batch.backfill.__main__ helpers.

Tests cover:
- _load_backfill_symbols falls back to hardcoded list when GCS raises
- _load_backfill_symbols returns symbols from GCS list[str] payload
- _load_backfill_symbols returns symbols from GCS list[dict] payload
- GCS path construction for daily stream includes source=vnstock partition
  and writes one blob per distinct date in the returned DataFrame
"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

# ---------------------------------------------------------------------------
# _load_backfill_symbols
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_backfill_symbols_falls_back_on_gcs_error(monkeypatch):
    """When GCS raises, should return the 30-symbol hardcoded fallback list."""
    mock_storage = MagicMock()
    mock_storage.return_value.bucket.return_value.blob.return_value.download_as_text.side_effect = (
        Exception("GCS unavailable")
    )
    with patch("google.cloud.storage.Client", mock_storage):
        from batch.backfill.__main__ import _load_backfill_symbols

        syms = _load_backfill_symbols("staging")

    assert isinstance(syms, list)
    assert len(syms) == 30
    assert "VNM" in syms
    assert "FPT" in syms


@pytest.mark.unit
def test_load_backfill_symbols_reads_list_of_strings(monkeypatch):
    """GCS returns list[str] — should be passed through directly."""
    payload = json.dumps(["AAA", "BBB", "CCC"])
    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = payload
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.return_value.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", mock_client):
        from batch.backfill.__main__ import _load_backfill_symbols

        syms = _load_backfill_symbols("staging")

    assert syms == ["AAA", "BBB", "CCC"]


@pytest.mark.unit
def test_load_backfill_symbols_reads_list_of_dicts(monkeypatch):
    """GCS returns list[dict] (same format as eod-symbols.json) — extract 'symbol' key."""
    payload = json.dumps(
        [
            {"symbol": "VNM", "asset_class": "equity", "exchange": "HOSE"},
            {"symbol": "VIC", "asset_class": "equity", "exchange": "HOSE"},
        ]
    )
    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = payload
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.return_value.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", mock_client):
        from batch.backfill.__main__ import _load_backfill_symbols

        syms = _load_backfill_symbols("staging")

    assert syms == ["VNM", "VIC"]


# ---------------------------------------------------------------------------
# Daily path construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_gcs_paths_contain_source_vnstock_and_one_blob_per_date():
    """_run_daily should call bucket.blob(...).upload_from_string twice for a 2-row
    DataFrame with two distinct dates, and each path must contain source=vnstock."""
    import asyncio

    # Two-row DataFrame simulating pull_daily output
    df = pl.DataFrame(
        {
            "date": [date(2021, 3, 1), date(2021, 3, 2)],
            "symbol": ["VNM", "VNM"],
            "asset_class": ["equity", "equity"],
            "exchange": ["HOSE", "HOSE"],
            "open": [100_000, 101_000],
            "high": [102_000, 103_000],
            "low": [99_000, 100_500],
            "close": [101_000, 102_000],
            "volume": [1_000_000, 900_000],
            "value": [101_000_000_000, 91_800_000_000],
            "foreign_buy_vol": [None, None],
            "foreign_sell_vol": [None, None],
        }
    )

    uploaded_keys: list[str] = []

    # Build fake bucket that records blob keys
    def fake_blob(key):
        b = MagicMock()
        b.upload_from_string.side_effect = lambda data, **kw: uploaded_keys.append(key)
        return b

    mock_bucket = MagicMock()
    mock_bucket.blob.side_effect = fake_blob
    mock_sem = asyncio.Semaphore(10)
    mock_tb = MagicMock()
    mock_tb.acquire = AsyncMock()

    with patch("batch.eod.vnstock_pulls.pull_daily", return_value=df):
        from batch.backfill.__main__ import _run_daily

        rows, errors = asyncio.run(
            _run_daily(mock_sem, mock_bucket, "VNM", date(2021, 3, 1), date(2021, 3, 2), mock_tb)
        )

    assert errors == []
    assert rows == 2
    assert len(uploaded_keys) == 2
    for key in uploaded_keys:
        assert "source=vnstock" in key
        assert "daily-ohlcv" in key
        assert "symbol=VNM" in key
    # Verify two distinct dates appear in paths
    assert any("date=2021-03-01" in k for k in uploaded_keys)
    assert any("date=2021-03-02" in k for k in uploaded_keys)
