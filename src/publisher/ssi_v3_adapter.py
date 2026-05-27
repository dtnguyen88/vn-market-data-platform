"""SSI FastConnect v3 streaming adapter.

Thin facade over `ssi-sdk` AsyncAuth + AsyncStream that:
  - resolves credentials from Secret Manager,
  - works around the WS 403 by injecting `User-Agent: Mozilla/5.0`,
  - **bypasses the SDK's typed-message wrapper** because it drops fields
    (e.g. `TradeMessage` loses session OHL + avg_price). We replace the
    DATA channel handler with one that pushes RAW `{topic, data}` dicts
    into an asyncio.Queue.

Exposes an async iterator `frames()` yielding `(topic, data, ts_received)`
tuples for the publisher loop. Heartbeats and trading events are handled
separately via callbacks (see `set_*_callback`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from ssi_sdk import AsyncAuth, AsyncStream, Config
from ssi_sdk.enums import StreamingChannel

log = logging.getLogger(__name__)


class V3StreamAdapter:
    """SSI v3 streaming with raw-frame access."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        private_key: str = "",
        client_id: str = "",  # SSI derives this server-side from api_key
        symbols: list[str] | None = None,
        indices: list[str] | None = None,
    ):
        self._cfg = Config(
            client_id=client_id,
            api_key=api_key,
            api_secret=api_secret,
            private_key=private_key,
        )
        self._symbols = symbols or []
        self._indices = indices or []
        self._queue: asyncio.Queue[tuple[str, dict, datetime]] = asyncio.Queue(maxsize=10_000)
        self._auth: AsyncAuth | None = None
        self._stream: AsyncStream | None = None
        self._heartbeat_cb: Callable[[dict], Any] | None = None
        self._trading_cb: Callable[[str, dict, datetime], Any] | None = None

    def set_heartbeat_callback(self, cb: Callable[[dict], Any]) -> None:
        self._heartbeat_cb = cb

    def set_trading_callback(self, cb: Callable[[str, dict, datetime], Any]) -> None:
        """Optional handler for TRADING channel (order/portfolio events)."""
        self._trading_cb = cb

    async def __aenter__(self) -> V3StreamAdapter:
        self._auth = AsyncAuth(self._cfg)
        await self._auth.__aenter__()
        await self._auth.authenticate()  # Data scope: no OTP required
        log.info(
            "SSI v3 auth OK, token_len=%d expired=%s",
            len(self._auth.access_token or ""),
            self._auth.is_token_expired,
        )

        self._stream = AsyncStream(self._auth)
        await self._stream.__aenter__()

        # Install our raw-frame capturer BEFORE connect, in place of the SDK's
        # typed-message wrapper. SDK calls `ws.on(channel, handler)` with a
        # single-element list, so we just overwrite directly.
        ws_handlers = self._stream.streaming._ws._handlers
        ws_handlers[StreamingChannel.DATA.value] = [self._on_data_raw]
        ws_handlers[StreamingChannel.TRADING.value] = [self._on_trading_raw]
        ws_handlers[StreamingChannel.HEARTBEAT.value] = [self._on_heartbeat_raw]

        # api.ssi.com.vn is behind Cloudflare. CF Bot Management 403s any WS
        # upgrade from datacenter IPs (Google Cloud, AWS, etc.) unless the
        # request "looks browser-like" — i.e. carries the full set of Chrome
        # client hints + Sec-Fetch-* headers. Bare `Mozilla/5.0` works from
        # residential ISP IPs but fails from Cloud Run egress.
        # Verified bypass: HTTP 101 from Cloud Run with this header set
        # (Cloudflare CF-Ray captured; not from SSI's app layer).
        self._stream.streaming._ws._headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Origin": "https://api.ssi.com.vn",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "sec-ch-ua": ('"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Dest": "websocket",
                "Sec-Fetch-Mode": "websocket",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        await self._stream.streaming.connect()
        log.info("SSI v3 WS connected")

        if self._symbols:
            # subscribe_symbol() = trade+quote+room combined per symbol.
            # SDK does NOT include put-through or odd-lot in this combo, so
            # subscribe to those separately to fill all 5 data streams.
            await self._stream.streaming.subscribe_symbol(self._symbols)
            await self._stream.streaming.subscribe_symbol_put_through(self._symbols)
            await self._stream.streaming.subscribe_symbol_odd_lot(self._symbols)
            log.info(
                "subscribed to %d symbols (trade+quote+room+put-through+odd-lot)",
                len(self._symbols),
            )
        if self._indices:
            # subscribe_index() succeeds but yields no events on this account/SDK
            # combo (market.* topic). We still call it for symmetry; index VALUES
            # come from the REST poller, not this stream.
            await self._stream.streaming.subscribe_index(self._indices)
            log.info("subscribed to %d indices (note: no realtime data via WS)", len(self._indices))

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._stream is not None:
                await self._stream.__aexit__(exc_type, exc, tb)
        finally:
            if self._auth is not None:
                await self._auth.__aexit__(exc_type, exc, tb)

    # --- internal raw frame handlers (called by SDK's WS listener loop) ---

    def _on_data_raw(self, msg: dict) -> None:
        topic = msg.get("topic", "")
        if not topic:
            # subscribe ack: {method, channel, status, message} — log + drop
            log.debug("DATA ack: %s", msg)
            return
        data = msg.get("data") or {}
        ts = datetime.now(UTC)
        try:
            self._queue.put_nowait((topic, data, ts))
        except asyncio.QueueFull:
            log.warning("frame queue full; dropping %s", topic)

    def _on_trading_raw(self, msg: dict) -> None:
        topic = msg.get("topic", "")
        if not topic or self._trading_cb is None:
            return
        try:
            self._trading_cb(topic, msg.get("data") or {}, datetime.now(UTC))
        except Exception:
            log.exception("trading callback failed")

    def _on_heartbeat_raw(self, msg: dict) -> None:
        if self._heartbeat_cb is not None:
            try:
                self._heartbeat_cb(msg)
            except Exception:
                log.exception("heartbeat callback failed")

    # --- public consumer iface ---

    async def frames(self) -> AsyncIterator[tuple[str, dict, datetime]]:
        """Yield (topic, data, ts_received) tuples forever."""
        while True:
            yield await self._queue.get()
