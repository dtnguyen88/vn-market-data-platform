"""Unit tests for alerter.telegram_client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alerter.telegram_client import TelegramClient, TelegramError


@pytest.fixture
def client():
    return TelegramClient(bot_token="123:abc", chat_id="987")


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"ok": True, "result": {"message_id": 42}}
    return r


def _error_response(status=500):
    r = MagicMock()
    r.status_code = status
    r.text = "Internal Server Error"
    r.json.return_value = {"ok": False, "description": "boom"}
    return r


@pytest.mark.unit
async def test_send_message_success(client):
    with patch("alerter.telegram_client.httpx.AsyncClient") as mock_cls:
        mock_inst = MagicMock()
        mock_inst.__aenter__ = AsyncMock(return_value=mock_inst)
        mock_inst.__aexit__ = AsyncMock(return_value=None)
        mock_inst.post = AsyncMock(return_value=_ok_response())
        mock_cls.return_value = mock_inst

        result = await client.send_message("hello")
        assert result == {"message_id": 42}
        # Verify URL + payload
        url_called = mock_inst.post.call_args.args[0]
        assert "bot123:abc/sendMessage" in url_called
        payload = mock_inst.post.call_args.kwargs["json"]
        assert payload["chat_id"] == "987"
        assert payload["text"] == "hello"
        assert payload["parse_mode"] == "Markdown"


@pytest.mark.unit
async def test_send_message_http_error(client):
    with patch("alerter.telegram_client.httpx.AsyncClient") as mock_cls:
        mock_inst = MagicMock()
        mock_inst.__aenter__ = AsyncMock(return_value=mock_inst)
        mock_inst.__aexit__ = AsyncMock(return_value=None)
        mock_inst.post = AsyncMock(return_value=_error_response(status=500))
        mock_cls.return_value = mock_inst

        with pytest.raises(TelegramError, match="HTTP 500"):
            await client.send_message("hello")


@pytest.mark.unit
async def test_send_message_api_ok_false(client):
    not_ok = MagicMock()
    not_ok.status_code = 200
    not_ok.json.return_value = {"ok": False, "description": "Bot is blocked"}
    with patch("alerter.telegram_client.httpx.AsyncClient") as mock_cls:
        mock_inst = MagicMock()
        mock_inst.__aenter__ = AsyncMock(return_value=mock_inst)
        mock_inst.__aexit__ = AsyncMock(return_value=None)
        mock_inst.post = AsyncMock(return_value=not_ok)
        mock_cls.return_value = mock_inst

        with pytest.raises(TelegramError, match="ok=false"):
            await client.send_message("hello")
