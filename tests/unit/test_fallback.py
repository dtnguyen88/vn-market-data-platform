import pytest
from shared.fallback import AllSourcesFailed, async_try_in_order, try_in_order


@pytest.mark.unit
def test_first_source_succeeds():
    result = try_in_order([lambda: "ok"])
    assert result == "ok"


@pytest.mark.unit
def test_falls_through_to_second():
    def fail():
        raise RuntimeError("boom")

    def ok():
        return 42

    assert try_in_order([fail, ok]) == 42


@pytest.mark.unit
def test_all_fail_raises_all_sources_failed():
    def fail1():
        raise RuntimeError("e1")

    def fail2():
        raise ValueError("e2")

    with pytest.raises(AllSourcesFailed) as exc:
        try_in_order([fail1, fail2])
    assert "e1" in str(exc.value) or "e2" in str(exc.value)


@pytest.mark.unit
def test_passes_args_kwargs():
    def add(a, b, mult=1):
        return (a + b) * mult

    assert try_in_order([add], 2, 3, mult=10) == 50


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_first_succeeds():
    async def ok():
        return "async-ok"

    result = await async_try_in_order([ok])
    assert result == "async-ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_falls_through():
    async def fail():
        raise RuntimeError("oops")

    async def ok():
        return 7

    assert await async_try_in_order([fail, ok]) == 7


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_all_fail():
    async def fail1():
        raise RuntimeError("e1")

    async def fail2():
        raise ValueError("e2")

    with pytest.raises(AllSourcesFailed):
        await async_try_in_order([fail1, fail2])
