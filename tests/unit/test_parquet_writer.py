"""Unit tests for writers.parquet_writer — Polars frame → Parquet bytes (zstd-3)."""

import io
from datetime import UTC, datetime

import polars as pl
import pytest
from shared.schemas import Exchange, IndexValue
from writers.parquet_writer import models_to_parquet


@pytest.mark.unit
def test_empty_returns_empty_bytes():
    assert models_to_parquet([]) == b""


@pytest.mark.unit
def test_roundtrip():
    iv = IndexValue(
        ts_event=datetime(2026, 4, 27, 9, 0, 0, tzinfo=UTC),
        ts_received=datetime(2026, 4, 27, 9, 0, 1, tzinfo=UTC),
        index_code="VNINDEX",
        exchange=Exchange.HOSE,
        value=1234.56,
        change=12.34,
        change_pct=1.01,
        total_volume=50_000_000,
        total_value=1_500_000_000_000,
        advance_count=220,
        decline_count=180,
        unchanged_count=50,
    )
    data = models_to_parquet([iv])
    assert len(data) > 0
    df = pl.read_parquet(io.BytesIO(data))
    assert df.shape[0] == 1
    assert df["index_code"][0] == "VNINDEX"
