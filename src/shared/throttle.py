"""Async token-bucket rate limiter.

One bucket per upstream source. `acquire()` blocks until tokens are available.
Tokens replenish continuously at `rate` per second up to `capacity`.
"""

import asyncio
import time


class TokenBucket:
    """Async token-bucket rate limiter.

    Args:
        rate: tokens replenished per second (steady-state RPS).
        capacity: maximum tokens (burst size).
    """

    def __init__(self, rate: float, capacity: int):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1) -> None:
        """Block until `n` tokens are available, then consume them."""
        if n > self.capacity:
            raise ValueError(f"requested {n} tokens exceeds capacity {self.capacity}")
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                deficit = n - self._tokens
                wait = deficit / self.rate
            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
