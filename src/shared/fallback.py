"""Multi-source fallback helpers.

Used to try a list of source functions (e.g. TCBS -> VCI -> SSI HTML for vnstock)
and return the first success. All failures are logged with structlog; if every
source fails, raises AllSourcesFailedError wrapping the individual exceptions.
"""

from collections.abc import Awaitable, Callable

import structlog

log = structlog.get_logger(__name__)


class AllSourcesFailedError(Exception):
    """Raised when every source in a fallback chain fails.

    `errors` attribute is a list of (source_name, exception) tuples.
    """

    def __init__(self, errors: list[tuple[str, BaseException]]):
        self.errors = errors
        msg = "; ".join(f"{name}: {err!r}" for name, err in errors)
        super().__init__(f"all sources failed: {msg}")


# Backward-compatible alias used by callers importing AllSourcesFailed
AllSourcesFailed = AllSourcesFailedError


def try_in_order[T](funcs: list[Callable[..., T]], *args, **kwargs) -> T:
    """Run each callable in order; return first success. Raise AllSourcesFailedError if all fail."""
    errors: list[tuple[str, BaseException]] = []
    for fn in funcs:
        name = getattr(fn, "__name__", repr(fn))
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log.warning("source failed", source=name, error=str(e))
            errors.append((name, e))
    raise AllSourcesFailedError(errors)


async def async_try_in_order[T](funcs: list[Callable[..., Awaitable[T]]], *args, **kwargs) -> T:
    """Async variant of try_in_order. Awaits each callable in order."""
    errors: list[tuple[str, BaseException]] = []
    for fn in funcs:
        name = getattr(fn, "__name__", repr(fn))
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            log.warning("source failed", source=name, error=str(e))
            errors.append((name, e))
    raise AllSourcesFailedError(errors)
