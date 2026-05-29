"""Unit tests for V3StreamAdapter.frames() WS-disconnect detection.

Bug: SSI bearer JWT TTL = 900s. After the token expires the WS gets booted
by SSI; SDK's listen task ends silently and our queue blocks forever.

Fix: frames() races queue.get() against the listen task and raises
WSDisconnectedError when the listen task ends → caller can reconnect.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from publisher.ssi_v3_adapter import V3StreamAdapter, WSDisconnectedError


def _make_adapter() -> V3StreamAdapter:
    """Build an adapter without entering __aenter__ (no real SSI auth)."""
    return V3StreamAdapter(
        api_key="k",
        api_secret="s",
        private_key="",
        symbols=["VIC"],
    )


async def _collect(adapter: V3StreamAdapter, n: int) -> list:
    """Drain n frames from adapter.frames()."""
    out = []
    async for frame in adapter.frames():
        out.append(frame)
        if len(out) >= n:
            break
    return out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_frames_yields_when_listen_task_alive():
    """frames() returns queued frames while the SDK listen task is still running."""
    adapter = _make_adapter()
    # Simulate a long-running SDK listen task
    adapter._listen_task = asyncio.create_task(asyncio.sleep(10))

    ts = datetime(2026, 5, 29, 2, 0, 0, tzinfo=UTC)
    await adapter._queue.put(("trade.VIC", {"price": 1000}, ts))
    await adapter._queue.put(("quote.VIC", {"bid": 999}, ts))

    out = await _collect(adapter, 2)

    assert len(out) == 2
    assert out[0][0] == "trade.VIC"
    assert out[1][0] == "quote.VIC"

    adapter._listen_task.cancel()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_frames_raises_wsdisconnected_when_listen_task_ends():
    """When the SDK listen task ends (clean WS close), frames() must raise
    WSDisconnectedError so the caller can reconnect with a fresh token."""
    adapter = _make_adapter()

    async def _fake_listen():
        # Simulate SDK's listen loop exiting after a brief moment
        await asyncio.sleep(0.05)

    adapter._listen_task = asyncio.create_task(_fake_listen())

    with pytest.raises(WSDisconnectedError):
        async for _ in adapter.frames():
            pass  # queue stays empty; only the listen task ending should drive us out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_frames_raises_even_with_pending_frames_when_listen_dies():
    """If listen task dies, we surface WSDisconnectedError promptly — leftover queue
    contents are abandoned (acceptable trade-off; reconnect will resubscribe)."""
    adapter = _make_adapter()

    async def _fake_listen():
        await asyncio.sleep(0.01)

    adapter._listen_task = asyncio.create_task(_fake_listen())
    # Wait for the listen task to actually complete before iterating, so the
    # race in frames() resolves to the listen branch deterministically.
    await asyncio.sleep(0.05)

    ts = datetime(2026, 5, 29, 2, 0, 0, tzinfo=UTC)
    await adapter._queue.put(("trade.VIC", {"price": 1000}, ts))

    with pytest.raises(WSDisconnectedError):
        async for _ in adapter.frames():
            pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test_frames_runtime_error_if_not_entered():
    """frames() requires __aenter__ to have set _listen_task."""
    adapter = _make_adapter()
    with pytest.raises(RuntimeError, match="frames\\(\\) called before"):
        async for _ in adapter.frames():
            pass
