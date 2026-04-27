"""Per-key in-memory buffer with size + age flush triggers."""

import time as _time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Entry:
    items: list[bytes] = field(default_factory=list)
    size_bytes: int = 0
    first_added: float = 0.0


class RingBuffer:
    """Buffers byte payloads keyed by partition string. Flushes on size or age."""

    def __init__(self, max_bytes: int, max_age_s: float):
        self.max_bytes = max_bytes
        self.max_age_s = max_age_s
        self._by_key: dict[str, _Entry] = defaultdict(_Entry)

    def add(self, item: bytes, key: str, now: float | None = None) -> None:
        e = self._by_key[key]
        if not e.items:
            e.first_added = now if now is not None else _time.time()
        e.items.append(item)
        e.size_bytes += len(item)

    def drain_if_ready(self, now: float) -> dict[str, list[bytes]]:
        """Return and remove all keys whose size or age threshold is exceeded."""
        ready: dict[str, list[bytes]] = {}
        keys = [
            k
            for k, e in self._by_key.items()
            if e.size_bytes >= self.max_bytes or (now - e.first_added) >= self.max_age_s
        ]
        for k in keys:
            ready[k] = self._by_key.pop(k).items
        return ready

    def drain_all(self) -> dict[str, list[bytes]]:
        """Return and remove all buffered items regardless of thresholds."""
        out = {k: e.items for k, e in self._by_key.items() if e.items}
        self._by_key.clear()
        return out
