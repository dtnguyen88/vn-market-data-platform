"""Symbol → shard hashing. Deterministic across deploys. Indices pinned to shard 0."""

import mmh3

NUM_SHARDS = 4

# Indices are low-volume; pin to shard 0 so we don't waste a publisher slot.
_INDEX_PREFIXES = ("VN", "HNX", "UPCOM")
_INDEX_EXACT = {
    "VNINDEX",
    "VN30",
    "VN100",
    "VNALL",
    "VNX50",
    "VNMID",
    "VNSML",
    "HNXINDEX",
    "HNX30",
    "HNXLCAP",
    "HNXMSCAP",
    "HNXSCAP",
    "UPCOMINDEX",
    "UPCOMLARGE",
    "UPCOMMEDIUM",
    "UPCOMSMALL",
    "UPCOMPREMIUM",
    "VNFIN",
    "VNCONS",
    "VNCOND",
    "VNENE",
    "VNHEALTH",
    "VNIND",
    "VNIT",
    "VNMAT",
    "VNREAL",
    "VNUTI",
    "VNTEL",
    "VNDIAMOND",
    "VNFINLEAD",
    "VNFINSELECT",
    "VNXALL",
}


def shard_for_symbol(symbol: str) -> int:
    """Return shard 0..NUM_SHARDS-1 for a given symbol."""
    if symbol in _INDEX_EXACT:
        return 0
    h, _ = mmh3.hash64(symbol.encode(), signed=False)
    return int(h % NUM_SHARDS)
