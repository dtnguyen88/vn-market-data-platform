"""SSI FastConnect Data WebSocket client.

Reconnect logic with exponential backoff. Subscription management on connect.

NOTE: SSI WS wire protocol is best-known but not yet validated against an active
subscription. Field names and message envelope (`type` / `data`, `auth` action,
etc.) are placeholders to be confirmed with SSI docs at production cutover.
"""

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import websockets

log = logging.getLogger(__name__)


# NOTE: URL unverified — confirm with SSI FastConnect Data documentation before go-live
SSI_WS_URL = "wss://fc-data.ssi.com.vn/realtime"  # confirm with SSI docs


class SsiWsClient:
    def __init__(self, username: str, password: str, symbols: list[str]):
        self.username = username
        self.password = password
        self.symbols = symbols
        self._reconnect_delay = 5.0

    async def stream(self) -> AsyncIterator[tuple[str, dict, datetime]]:
        """Yield (channel, payload, ts_received) tuples. Reconnects on disconnect."""
        while True:
            try:
                async with websockets.connect(SSI_WS_URL) as ws:
                    await self._authenticate(ws)
                    await self._subscribe(ws)
                    self._reconnect_delay = 5.0
                    async for raw in ws:
                        ts = datetime.now(UTC)
                        msg = json.loads(raw)
                        # NOTE: envelope keys ("type", "data") are unverified — update once SSI
                        # confirms the exact wire format via real subscription testing.
                        channel = msg.get("type")  # "tick" | "l1" | "l2" | "index"
                        payload = msg.get("data", {})
                        if channel and payload:
                            yield (channel, payload, ts)
            except (websockets.ConnectionClosed, OSError) as e:
                log.warning(
                    "ws disconnect: %s; reconnecting in %.1fs",
                    e,
                    self._reconnect_delay,
                )
                await asyncio.sleep(
                    self._reconnect_delay * (1 + random.uniform(-0.2, 0.2))  # noqa: S311  # jitter, not security-sensitive
                )
                self._reconnect_delay = min(self._reconnect_delay * 2, 120.0)

    async def _authenticate(self, ws) -> None:
        # NOTE: auth action name and response shape unverified — confirm with SSI docs
        await ws.send(
            json.dumps(
                {
                    "action": "auth",
                    "username": self.username,
                    "password": self.password,
                }
            )
        )
        resp = json.loads(await ws.recv())
        if resp.get("status") != "ok":
            raise RuntimeError(f"SSI auth failed: {resp}")

    async def _subscribe(self, ws) -> None:
        # NOTE: subscribe action, channels list, and symbols format are unverified
        await ws.send(
            json.dumps(
                {
                    "action": "subscribe",
                    "channels": ["tick", "l1", "l2", "index"],
                    "symbols": self.symbols,
                }
            )
        )
