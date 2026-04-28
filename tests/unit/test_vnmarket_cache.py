"""Unit tests for vnmarket.cache.ParquetCache (uses tmp_path)."""

import pytest
from vnmarket.cache import ParquetCache


@pytest.mark.unit
def test_put_and_get(tmp_path):
    cache = ParquetCache(root=tmp_path, cap_bytes=10_000_000)
    cache.put("gs://bucket/a.parquet", b"x" * 100)
    assert cache.get("gs://bucket/a.parquet") == b"x" * 100


@pytest.mark.unit
def test_get_missing_returns_none(tmp_path):
    cache = ParquetCache(root=tmp_path)
    assert cache.get("gs://bucket/missing") is None


@pytest.mark.unit
def test_eviction_when_over_cap(tmp_path):
    cache = ParquetCache(root=tmp_path, cap_bytes=300)
    cache.put("a", b"x" * 200)
    cache.put("b", b"x" * 200)  # over cap; eviction kicks in
    # a may be evicted (oldest); total size <= cap
    assert cache.total_size() <= 300


@pytest.mark.unit
def test_atomic_write_no_partial_file(tmp_path):
    cache = ParquetCache(root=tmp_path)
    cache.put("k1", b"hello")
    # No .tmp file should remain
    assert list(tmp_path.rglob("*.tmp")) == []


@pytest.mark.unit
def test_file_perms_owner_only(tmp_path):
    cache = ParquetCache(root=tmp_path)
    path = cache.put("k1", b"hello")
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
