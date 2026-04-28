"""Telegram Bot API client.

Wraps `sendMessage`. No batching; one request per alert. Caller handles
rate-limiting (TokenBucket) and dedup.
"""

import httpx
import structlog

log = structlog.get_logger(__name__)

API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    """Raised when Telegram returns a non-2xx status or ok=false response."""


class TelegramClient:
    """Send messages to a single Telegram chat via Bot API."""

    def __init__(self, bot_token: str, chat_id: str, timeout_s: float = 10.0):
        self._token = bot_token
        self._chat_id = chat_id
        self._timeout = timeout_s

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> dict:
        """POST sendMessage. Returns the API result dict on success.

        Raises TelegramError on non-2xx status or ok=false response.
        """
        url = f"{API_BASE}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise TelegramError(f"telegram HTTP {resp.status_code}: {resp.text}")
        body = resp.json()
        if not body.get("ok"):
            raise TelegramError(f"telegram ok=false: {body}")
        return body.get("result", {})
