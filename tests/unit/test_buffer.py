"""Unit tests for writers.buffer.RingBuffer — size + age flush triggers."""

import time

import pytest
from writers.buffer import RingBuffer


@pytest.mark.unit
def test_buffer_flushes_on_size_threshold():
    buf = RingBuffer(max_bytes=100, max_age_s=60)
    for _ in range(10):
        buf.add(b"x" * 20, key="VNM")
    flushed = buf.drain_if_ready(now=time.time())
    assert "VNM" in flushed and len(flushed["VNM"]) == 10


@pytest.mark.unit
def test_buffer_flushes_on_age_threshold():
    buf = RingBuffer(max_bytes=10_000, max_age_s=1)
    buf.add(b"x", key="VNM", now=1000.0)
    flushed = buf.drain_if_ready(now=1002.0)
    assert "VNM" in flushed


@pytest.mark.unit
def test_buffer_does_not_flush_when_below_thresholds():
    buf = RingBuffer(max_bytes=10_000, max_age_s=60)
    buf.add(b"x", key="VNM")
    flushed = buf.drain_if_ready(now=time.time())
    assert flushed == {}


@pytest.mark.unit
def test_drain_all_clears_buffer():
    buf = RingBuffer(max_bytes=10_000, max_age_s=60)
    buf.add(b"x", key="A")
    buf.add(b"y", key="B")
    out = buf.drain_all()
    assert set(out.keys()) == {"A", "B"}
    assert buf.drain_if_ready(now=time.time() + 9999) == {}
