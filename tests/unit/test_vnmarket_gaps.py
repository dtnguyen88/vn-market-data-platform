"""Unit tests for vnmarket.gaps.load_gaps."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from vnmarket.gaps import load_gaps


@pytest.mark.unit
@patch("vnmarket.gaps.storage.Client")
def test_load_gaps_returns_empty_when_blob_missing(mock_cls):
    blob = MagicMock()
    blob.exists.return_value = False
    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_cls.return_value = client

    result = load_gaps("p", "staging", "ticks")
    assert result == []


@pytest.mark.unit
@patch("vnmarket.gaps.storage.Client")
def test_load_gaps_parses_jsonl(mock_cls):
    payload = (
        '{"start":"2024-01-01","end":"2024-01-15","reason":"SSI not available"}\n'
        '{"start":"2024-06-01","end":"2024-06-01","reason":"feed outage"}\n'
    )
    blob = MagicMock()
    blob.exists.return_value = True
    blob.download_as_text.return_value = payload
    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_cls.return_value = client

    result = load_gaps("p", "staging", "ticks")
    assert len(result) == 2
    assert result[0]["start"] == date(2024, 1, 1)
    assert result[0]["end"] == date(2024, 1, 15)
    assert result[1]["reason"] == "feed outage"


@pytest.mark.unit
@patch("vnmarket.gaps.storage.Client")
def test_load_gaps_skips_invalid_json(mock_cls):
    blob = MagicMock()
    blob.exists.return_value = True
    blob.download_as_text.return_value = '{"valid":1}\nnot-json\n{"start":"2024-01-01"}\n'
    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_cls.return_value = client

    result = load_gaps("p", "staging", "ticks")
    # 2 valid records (1 and 3); the middle malformed line skipped.
    assert len(result) == 2


@pytest.mark.unit
@patch("vnmarket.gaps.storage.Client")
def test_load_gaps_returns_empty_on_exception(mock_cls):
    mock_cls.side_effect = RuntimeError("auth failed")
    result = load_gaps("p", "staging", "ticks")
    assert result == []
