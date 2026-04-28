"""Unit tests for batch.backfill.planner."""

from datetime import date

import pytest
from batch.backfill.planner import daterange, plan_chunks


@pytest.mark.unit
def test_daterange_inclusive():
    days = list(daterange(date(2024, 1, 1), date(2024, 1, 3)))
    assert days == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]


@pytest.mark.unit
def test_plan_chunks_evenly_divides():
    chunks = plan_chunks(date(2024, 1, 1), date(2024, 1, 10), 5)
    assert len(chunks) == 5
    # 10 days / 5 chunks = 2 each
    for s, e in chunks:
        assert (e - s).days == 1


@pytest.mark.unit
def test_plan_chunks_handles_remainder():
    # 10 days / 3 chunks = [4, 3, 3]
    chunks = plan_chunks(date(2024, 1, 1), date(2024, 1, 10), 3)
    assert len(chunks) == 3
    sizes = [(e - s).days + 1 for s, e in chunks]
    assert sum(sizes) == 10
    assert sizes[0] >= sizes[-1]


@pytest.mark.unit
def test_plan_chunks_more_tasks_than_days():
    chunks = plan_chunks(date(2024, 1, 1), date(2024, 1, 3), 10)
    # Should clamp to 3 chunks of 1 day each
    assert len(chunks) == 3


@pytest.mark.unit
def test_plan_chunks_invalid_num_tasks():
    with pytest.raises(ValueError):
        plan_chunks(date(2024, 1, 1), date(2024, 1, 5), 0)
