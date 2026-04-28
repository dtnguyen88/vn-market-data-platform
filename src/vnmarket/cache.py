"""Local LRU Parquet cache for vnmarket SDK.

Stores downloaded blobs keyed by their GCS URI. Eviction triggered when total
size exceeds the configured cap; oldest-mtime files are removed first.

Thread-safety: not guaranteed; intended for single-process notebook use.
"""

import hashlib
from pathlib import Path

from ._config import CACHE_DIR, DEFAULT_CACHE_BYTES


def _key_to_path(key: str, root: Path = CACHE_DIR) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:32]
    return root / h[:2] / f"{h}.parquet"


class ParquetCache:
    """File-based LRU cache for parquet blobs."""

    def __init__(self, root: Path | str = CACHE_DIR, cap_bytes: int = DEFAULT_CACHE_BYTES):
        self.root = Path(root)
        self.cap_bytes = cap_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> bytes | None:
        path = _key_to_path(key, self.root)
        if not path.exists():
            return None
        # Update mtime so this is "recently used"
        path.touch()
        return path.read_bytes()

    def put(self, key: str, data: bytes) -> Path:
        path = _key_to_path(key, self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp + rename
        tmp = path.with_suffix(".parquet.tmp")
        tmp.write_bytes(data)
        tmp.chmod(0o600)
        tmp.replace(path)
        self._evict_if_needed()
        return path

    def _evict_if_needed(self) -> None:
        files = sorted(self.root.rglob("*.parquet"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        while total > self.cap_bytes and files:
            victim = files.pop(0)
            total -= victim.stat().st_size
            victim.unlink(missing_ok=True)

    def total_size(self) -> int:
        return sum(p.stat().st_size for p in self.root.rglob("*.parquet"))
