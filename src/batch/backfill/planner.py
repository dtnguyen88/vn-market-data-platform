"""Date-range planner. Splits a backfill range into N chunks for task array."""

from collections.abc import Iterator
from datetime import date, timedelta


def daterange(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def plan_chunks(start: date, end: date, num_tasks: int) -> list[tuple[date, date]]:
    """Split [start, end] into roughly equal-sized contiguous date chunks for `num_tasks`."""
    if num_tasks < 1:
        raise ValueError("num_tasks must be >=1")
    days = list(daterange(start, end))
    if not days:
        return []
    if num_tasks > len(days):
        num_tasks = len(days)
    chunk_size = len(days) // num_tasks
    extra = len(days) % num_tasks
    chunks: list[tuple[date, date]] = []
    i = 0
    for t in range(num_tasks):
        size = chunk_size + (1 if t < extra else 0)
        if size == 0:
            continue
        chunks.append((days[i], days[i + size - 1]))
        i += size
    return chunks
