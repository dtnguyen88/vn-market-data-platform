"""Telegram alerter entrypoint.

Receives Pub/Sub push at POST /alert. Dedupes via Firestore. Rate-limits to
30 msg/min (Telegram Bot API cap). Sends via TelegramClient.

Env:
  GCP_PROJECT_ID             informational; used in log-link
  TELEGRAM_BOT_TOKEN_SECRET  secret name; default "telegram-bot-token"
  TELEGRAM_CHAT_ID_SECRET    secret name; default "telegram-chat-id"
"""

import base64
import json
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from shared.throttle import TokenBucket

from .dedupe import AlertDeduper
from .formatter import format_alert
from .telegram_client import TelegramClient, TelegramError

log = structlog.get_logger(__name__)

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
TG_TOKEN_SECRET = os.environ.get("TELEGRAM_BOT_TOKEN_SECRET", "telegram-bot-token")
TG_CHAT_SECRET = os.environ.get("TELEGRAM_CHAT_ID_SECRET", "telegram-chat-id")

# Module-level singletons initialised in lifespan
_state: dict = {}


def _resolve_secret(client, project_id: str, secret_name: str) -> str:
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy-import GCP libs so module loads cleanly in test environments where
    # google-cloud-firestore / google-cloud-secretmanager are not installed.
    from google.cloud import firestore, secretmanager

    sm = secretmanager.SecretManagerServiceClient()
    bot_token = _resolve_secret(sm, PROJECT_ID, TG_TOKEN_SECRET)
    chat_id = _resolve_secret(sm, PROJECT_ID, TG_CHAT_SECRET)
    fs = firestore.Client(project=PROJECT_ID)
    _state["telegram"] = TelegramClient(bot_token, chat_id)
    _state["deduper"] = AlertDeduper(fs)
    # Telegram cap = 30 msg/min = 0.5/s; capacity = 30 (1 min burst)
    _state["bucket"] = TokenBucket(rate=0.5, capacity=30)
    log.info("alerter ready")
    yield
    log.info("alerter shutdown")


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/alert")
async def receive_alert(req: Request):
    """Pub/Sub push handler. Body envelope: {message: {data: base64, attributes: {...}}}."""
    envelope = await req.json()
    msg = envelope.get("message", {})
    raw = msg.get("data", "")
    attrs = msg.get("attributes", {}) or {}
    try:
        body = base64.b64decode(raw).decode("utf-8")
    except Exception as e:
        log.warning("base64 decode failed", error=str(e))
        return {"status": "rejected", "reason": "invalid base64"}

    payload = _parse_payload(body, attrs)
    name = payload["name"]
    severity = payload["severity"]
    body_text = payload["body"]
    scope = payload.get("scope", "")
    source = payload.get("source", attrs.get("source"))
    extra = payload.get("extra", {})

    deduper = _state["deduper"]
    bucket = _state["bucket"]
    tg = _state["telegram"]

    alert_key = f"{name}|{severity}|{scope}"
    if not deduper.should_send(alert_key, severity):
        log.info("alert deduped", key=alert_key)
        return {"status": "deduped"}

    await bucket.acquire()
    msg_text = format_alert(
        severity,
        name,
        body_text,
        project_id=PROJECT_ID,
        source=source,
        extra=extra,
    )
    try:
        await tg.send_message(msg_text)
    except TelegramError as e:
        log.error("telegram send failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "sent"}


def _parse_payload(body: str, attrs: dict) -> dict:
    """Accept JSON body OR plain string. Merge attrs as fallback into payload."""
    try:
        payload = json.loads(body)
        if isinstance(payload, dict):
            return {
                "name": payload.get("name") or attrs.get("alert_name", "unknown"),
                "severity": payload.get("severity") or attrs.get("severity", "info"),
                "body": payload.get("body") or body,
                "scope": payload.get("scope") or attrs.get("scope", ""),
                "source": payload.get("source") or attrs.get("source"),
                "extra": payload.get("extra", {}),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    # Plain-string body — all fields come from attrs
    return {
        "name": attrs.get("alert_name", attrs.get("source", "unknown")),
        "severity": attrs.get("severity", "info"),
        "body": body,
        "scope": attrs.get("scope", ""),
        "source": attrs.get("source"),
        "extra": {},
    }
