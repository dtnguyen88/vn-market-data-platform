"""Historical clients for SSI (placeholder) + reuse of vnstock pullers from Phase 04."""

import polars as pl


class NotAvailableError(Exception):
    """Raised when an SSI historical endpoint doesn't have data for the requested range."""


def pull_history_ticks(symbol: str, start, end) -> pl.DataFrame:
    """SSI FC historical ticks. v1 stub: raises NotAvailableError. Real impl wraps SSI REST API."""
    raise NotAvailableError("SSI historical ticks not yet wired; record permanent gap")


def pull_history_quotes_l1(symbol: str, start, end) -> pl.DataFrame:
    raise NotAvailableError("SSI historical L1 not yet wired; record permanent gap")


def pull_history_quotes_l2(symbol: str, start, end) -> pl.DataFrame:
    raise NotAvailableError("SSI historical L2 not yet wired; record permanent gap")


def pull_history_indices(symbol: str, start, end) -> pl.DataFrame:
    raise NotAvailableError("SSI historical indices not yet wired; record permanent gap")
