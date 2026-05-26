"""SSI FastConnect v3 probe — capture real wire shapes via the official ssi-sdk.

Connects to wss://api.ssi.com.vn/ws/v3, subscribes to a small handful of liquid
symbols + indices, and dumps every callback message to stdout AND to a JSONL
corpus file. Used to:

  (1) confirm auth works with our creds (and figure out client_id semantics),
  (2) capture the actual typed-message field shapes (TradeMessage, QuoteMessage,
      MarketStatusMessage, ForeignRoomMessage, etc.) — quote depth, presence of
      trade_id / match_type / seq fields, exact timestamp format, etc.,
  (3) serve as the permanent "is the feed up?" diagnostic.

Run during VN market hours (09:00-11:30, 13:00-14:45 ICT) for live data.
Outside hours: auth + connect should still succeed, you just won't see ticks.

Usage:
    uv run python scripts/ssi-fc-v3-probe.py [--seconds 90] [--out /tmp/ssi.jsonl]

Reads creds from Secret Manager in project vn-market-platform-staging:
    ssi-fc-api-key, ssi-fc-api-secret, ssi-fc-rsa-private-key
Optional override via env: SSI_API_KEY, SSI_API_SECRET, SSI_PRIVATE_KEY, SSI_CLIENT_ID
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import enum
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ssi_sdk import AsyncAuth, AsyncStream, Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ssi-probe")

PROJECT = "vn-market-platform-staging"
DEFAULT_SYMBOLS = ["VNM", "VIC", "HPG", "SSI", "MWG"]
DEFAULT_INDICES = ["VNINDEX", "VN30"]


def _resolve_secret(name: str, env_var: str) -> str:
    """Env var wins (for fast iteration); fall back to Secret Manager."""
    if v := os.environ.get(env_var):
        return v
    from google.cloud import secretmanager  # local import to keep CLI snappy

    client = secretmanager.SecretManagerServiceClient()
    full = f"projects/{PROJECT}/secrets/{name}/versions/latest"
    return client.access_secret_version(name=full).payload.data.decode()


def _to_jsonable(obj: Any) -> Any:
    """Best-effort serialize SDK typed messages (dataclass / pydantic / dict)."""
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value if isinstance(obj.value, str | int | float | bool) else str(obj)
    if isinstance(obj, list | tuple):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj):
        return _to_jsonable(dataclasses.asdict(obj))
    if hasattr(obj, "model_dump"):  # pydantic v2
        return _to_jsonable(obj.model_dump(mode="json"))
    return str(obj)


async def run(seconds: int, out_path: Path) -> None:
    api_key = _resolve_secret("ssi-fc-api-key", "SSI_API_KEY")
    api_secret = _resolve_secret("ssi-fc-api-secret", "SSI_API_SECRET")
    private_key = _resolve_secret("ssi-fc-rsa-private-key", "SSI_PRIVATE_KEY")
    # client_id unknown — try empty first; fall back to api_key if SDK rejects.
    client_id = os.environ.get("SSI_CLIENT_ID", "")

    log.info("connecting to SSI FC v3 (api_key=%s…%s)", api_key[:4], api_key[-4:])
    cfg = Config(
        client_id=client_id, api_key=api_key, api_secret=api_secret, private_key=private_key
    )

    counts: dict[str, int] = {}
    out_fp = out_path.open("w", encoding="utf-8")

    def _record(kind: str, msg: Any) -> None:
        counts[kind] = counts.get(kind, 0) + 1
        rec = {
            "ts_received": datetime.now(UTC).isoformat(),
            "kind": kind,
            "type": type(msg).__name__,
            "msg": _to_jsonable(msg),
        }
        out_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out_fp.flush()
        # Print first 2 of each kind to stdout so we can eyeball field shape
        if counts[kind] <= 2:
            log.info("[%s #%d type=%s] %s", kind, counts[kind], type(msg).__name__, rec["msg"])

    try:
        async with AsyncAuth(cfg) as auth:
            try:
                await auth.authenticate()  # Data-only: no OTP needed per SDK docs
            except Exception as e:
                log.error("auth.authenticate() failed: %r", e)
                log.info("retrying with client_id=api_key as fallback")
                cfg2 = Config(
                    client_id=api_key,
                    api_key=api_key,
                    api_secret=api_secret,
                    private_key=private_key,
                )
                async with AsyncAuth(cfg2) as auth2:
                    await auth2.authenticate()
                    auth = auth2
                    raise SystemExit(
                        "auth retry path needs structural change; aborting probe"
                    ) from e
            log.info(
                "auth OK, access_token len=%d expired=%s",
                len(auth.access_token or ""),
                auth.is_token_expired,
            )

            async with AsyncStream(auth) as stream:
                stream.streaming.on_data = lambda m: _record("typed", m)
                stream.streaming.on_heartbeat = lambda m: _record("heartbeat", m)
                stream.streaming.on_trading = lambda m: _record("trading", m)

                # Wrap the SDK's installed DATA handler so we ALSO record raw frames.
                # `_handlers[channel]` is a single-element list — replacing it with a
                # composite gives us both raw + typed for every message.
                _sdk_wrap = stream.streaming._ws._handlers["DATA"][0]

                def _both(msg):
                    _record("raw", msg)
                    return _sdk_wrap(msg)

                stream.streaming._ws._handlers["DATA"] = [_both]

                # SSI WS rejects requests without a browser-style User-Agent.
                stream.streaming._ws._headers["User-Agent"] = "Mozilla/5.0"

                await stream.streaming.connect()
                log.info(
                    "WS connected; subscribing symbols=%s indices=%s",
                    DEFAULT_SYMBOLS,
                    DEFAULT_INDICES,
                )
                await stream.streaming.subscribe_symbol(DEFAULT_SYMBOLS)
                await stream.streaming.subscribe_index(DEFAULT_INDICES)

                log.info("listening for %ds…", seconds)
                try:
                    await asyncio.wait_for(stream.streaming.wait(), timeout=seconds)
                except TimeoutError:
                    pass
    finally:
        out_fp.close()
        log.info("=== probe summary ===")
        for k, v in sorted(counts.items()):
            log.info("  %s: %d msgs", k, v)
        log.info("corpus: %s", out_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=90)
    default_out = Path("/tmp") / f"ssi-probe-{int(datetime.now().timestamp())}.jsonl"  # noqa: S108
    ap.add_argument("--out", type=Path, default=default_out)
    args = ap.parse_args()
    asyncio.run(run(args.seconds, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
