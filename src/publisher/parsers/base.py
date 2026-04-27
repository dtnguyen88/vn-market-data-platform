"""Common parser utilities for SSI WebSocket message parsing."""

from datetime import UTC, datetime


def epoch_ms_to_dt(ms: int) -> datetime:
    """Convert SSI epoch-ms timestamp to UTC datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)
