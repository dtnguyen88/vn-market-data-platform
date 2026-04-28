"""Firestore-backed alert dedup with severity-based TTL.

Collection: `alert_dedupe`
Doc id: alert_key (sanitized to Firestore-safe chars)
Doc fields:
  - expires_at (Timestamp): when this dedup window ends
  - severity (string): for audit
"""

from datetime import UTC, datetime, timedelta

import structlog

log = structlog.get_logger(__name__)

TTL_SECONDS = {
    "critical": 0,  # never dedupe
    "error": 10 * 60,
    "warning": 10 * 60,
    "info": 60 * 60,
    "debug": 5 * 60,
}


def _ttl_for(severity: str) -> int:
    return TTL_SECONDS.get(severity, 10 * 60)


def _sanitize_key(alert_key: str) -> str:
    """Firestore doc IDs cannot contain '/'; replace + truncate to 1500 bytes."""
    return alert_key.replace("/", "_")[:1500]


class AlertDeduper:
    """Firestore-backed dedup; writes a doc per alert_key with TTL."""

    COLLECTION = "alert_dedupe"

    def __init__(self, firestore_client) -> None:
        self._client = firestore_client

    def should_send(self, alert_key: str, severity: str) -> bool:
        """Return True if alert should be sent; False if currently within dedup window.

        critical severity bypasses dedup (always returns True).
        """
        if severity == "critical":
            return True
        ttl = _ttl_for(severity)
        if ttl <= 0:
            return True
        now = datetime.now(UTC)
        doc_id = _sanitize_key(alert_key)
        doc_ref = self._client.collection(self.COLLECTION).document(doc_id)
        snap = doc_ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            expires_at = data.get("expires_at")
            if expires_at and expires_at > now:
                log.debug("alert deduped", alert_key=alert_key, expires_at=str(expires_at))
                return False
        doc_ref.set(
            {
                "expires_at": now + timedelta(seconds=ttl),
                "severity": severity,
            }
        )
        return True
