# Symbol shard manifests

Per-shard subscription lists for the realtime-publisher Cloud Run services.

## Files

- `symbols-shard-0.json` — symbols that hash to shard 0 (also receives all indices)
- `symbols-shard-1.json` — shard 1
- `symbols-shard-2.json` — shard 2
- `symbols-shard-3.json` — shard 3

The grouping is determined by `shard_for_symbol(symbol)` from `src/publisher/shard.py` (mmh3 mod 4, with indices pinned to shard 0).

## Provenance

This is a **representative sample** (~70 symbols). For production, replace with the full ~1,600-symbol VN universe filtered through `shard_for_symbol`. Generate with:

```python
from publisher.shard import NUM_SHARDS, shard_for_symbol
import json
universe = [...]  # full VN listed universe + indices + futures
buckets = [[] for _ in range(NUM_SHARDS)]
for sym in universe:
    buckets[shard_for_symbol(sym)].append(sym)
for i, syms in enumerate(buckets):
    with open(f"infra/symbols/symbols-shard-{i}.json", "w") as f:
        json.dump(sorted(syms), f, indent=2)
```

After regenerating, `terraform apply` re-uploads to GCS at `gs://vn-market-lake-{env}/_ops/reference/`.
