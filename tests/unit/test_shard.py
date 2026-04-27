import pytest
from publisher.shard import NUM_SHARDS, shard_for_symbol


@pytest.mark.unit
def test_shard_in_range():
    for sym in ["VNM", "VIC", "VHM", "FPT", "VN30F1M", "VNINDEX"]:
        s = shard_for_symbol(sym)
        assert 0 <= s < NUM_SHARDS


@pytest.mark.unit
def test_shard_deterministic():
    assert shard_for_symbol("VNM") == shard_for_symbol("VNM")


@pytest.mark.unit
def test_indices_pinned_to_shard_0():
    for idx in ["VNINDEX", "VN30", "VN100", "HNXINDEX", "UPCOMINDEX"]:
        assert shard_for_symbol(idx) == 0


@pytest.mark.unit
def test_distribution_roughly_uniform():
    syms = [f"SYM{i:04d}" for i in range(1600)]
    counts = [0] * NUM_SHARDS
    for s in syms:
        counts[shard_for_symbol(s)] += 1
    avg = 1600 / NUM_SHARDS
    for c in counts:
        assert avg * 0.7 < c < avg * 1.3, f"skewed distribution: {counts}"
