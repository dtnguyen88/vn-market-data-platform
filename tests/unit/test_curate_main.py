"""Unit tests for curate.__main__ entrypoint."""

from datetime import date

import pytest
from curate.__main__ import _build_uris


@pytest.mark.unit
def test_build_uris_ticks():
    raw, curated = _build_uris("ticks", date(2026, 4, 28), "staging")
    assert raw == "gs://vn-market-lake-staging/raw/ticks/date=2026-04-28/**/*.parquet"
    assert (
        curated == "gs://vn-market-lake-staging/curated/ticks/date=2026-04-28/_curate_run.parquet"
    )


@pytest.mark.unit
def test_build_uris_daily_ohlcv():
    raw, curated = _build_uris("daily-ohlcv", date(2026, 4, 28), "prod")
    assert "year=2026" in raw
    assert "year=2026" in curated


@pytest.mark.unit
def test_build_uris_quotes_l2_has_hour_partition():
    raw, _ = _build_uris("quotes-l2", date(2026, 4, 28), "staging")
    assert "raw/quotes-l2/date=2026-04-28" in raw


@pytest.mark.unit
def test_build_uris_unknown_stream_raises():
    with pytest.raises(ValueError, match="unknown stream"):
        _build_uris("invalid-stream", date(2026, 4, 28), "staging")
