"""Config: cache dir, default project, env."""

import os
from pathlib import Path

CACHE_DIR = Path(os.environ.get("VNMARKET_CACHE_DIR", str(Path.home() / ".vnmarket" / "cache")))
DEFAULT_CACHE_BYTES = int(
    os.environ.get("VNMARKET_CACHE_BYTES", str(10 * 1024 * 1024 * 1024))  # 10 GB
)
