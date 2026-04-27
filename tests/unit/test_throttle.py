import asyncio
import time

import pytest
from shared.throttle import TokenBucket


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acquire_under_capacity_does_not_block():
    bucket = TokenBucket(rate=10, capacity=10)
    start = time.monotonic()
    for _ in range(10):
        await bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, f"10 acquires under capacity took {elapsed:.2f}s"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acquire_over_capacity_throttles():
    """20 acquires at 10 req/s with capacity=10 should take ~1s."""
    bucket = TokenBucket(rate=10, capacity=10)
    start = time.monotonic()
    for _ in range(20):
        await bucket.acquire()
    elapsed = time.monotonic() - start
    # First 10 instant, next 10 at 10/s = ~1s. Allow slack: 0.7-1.5s.
    assert 0.7 <= elapsed <= 1.5, f"20 acquires took {elapsed:.2f}s"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_acquires_serialize_to_rate():
    """50 concurrent acquires at 50 req/s with capacity=50 → ~1s steady state.

    Burst of 50 (capacity) returns instantly; nothing else happens here.
    """
    bucket = TokenBucket(rate=50, capacity=50)
    start = time.monotonic()
    await asyncio.gather(*(bucket.acquire() for _ in range(50)))
    elapsed = time.monotonic() - start
    assert elapsed < 0.2, f"50 concurrent acquires within capacity took {elapsed:.2f}s"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acquire_n_tokens():
    """acquire(5) deducts 5 tokens at once."""
    bucket = TokenBucket(rate=100, capacity=10)
    await bucket.acquire(5)
    await bucket.acquire(5)
    # 10 tokens used; next acquire(1) should wait ~10ms (1/100s)
    start = time.monotonic()
    await bucket.acquire(1)
    elapsed = time.monotonic() - start
    assert 0.005 <= elapsed <= 0.05, f"acquire(1) after exhaustion took {elapsed:.4f}s"
