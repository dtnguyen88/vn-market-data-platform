"""Polars frame → Parquet bytes (zstd-3). Supports empty input."""

import io

import polars as pl
from pydantic import BaseModel


def models_to_parquet(models: list[BaseModel]) -> bytes:
    """Serialize a list of Pydantic models to Parquet bytes with zstd-3 compression.

    Returns empty bytes when models list is empty.
    Uses model_dump(mode='json') so timezone-aware datetimes serialize to ISO strings
    that Polars accepts via from_dicts.
    """
    if not models:
        return b""
    rows = [m.model_dump(mode="json") for m in models]
    df = pl.from_dicts(rows)
    buf = io.BytesIO()
    df.write_parquet(buf, compression="zstd", compression_level=3, statistics=True)
    return buf.getvalue()
