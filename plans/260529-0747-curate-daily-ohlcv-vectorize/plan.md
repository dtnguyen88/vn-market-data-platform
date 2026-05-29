# Curate Daily OHLCV — Vectorize Adjustments

## Problem

Cloud Run job `curate --stream=daily-ohlcv` times out at 30-min limit. Daily 16:30 ICT scheduled curate failing ~30 days. `vnmarket.daily_ohlcv_native` stale: last bar 2026-04-29, today 2026-05-29. Raw GCS partitions through 2026-05-28 exist; only curate→external→native pipeline broken.

## Root Cause

`src/curate/adjustments.py::apply_adjustments` does per-symbol Python loop with `map_elements` UDF over ~2000 symbols × ~1500 trading days (~3M rows). Python-UDF + Python `for sym in ...` loop is O(symbols × days) wall-clock and bursts the 30-min Cloud Run cap.

## Approach (KISS)

Single-phase refactor: replace Python loop in `apply_adjustments` with polars-native expression. No new partitioning scheme, no watermarking, no incremental scan — just vectorize.

**Algorithm (vectorized):**
- For each symbol, factors are sparse (mean ~3–10 per symbol).
- Per row need `Π factor(action)` where `ex_date > date`.
- Implement as `join` on `symbol`, filter `ex_date > date`, `group_by([symbol, date])` then aggregate with `pl.col("factor").product()`. Left-join back; missing rows = factor 1.0. Multiply by `close`.

## Constraints

- Backward-adjustment semantics preserved exactly — existing `tests/unit/test_adjustments.py` MUST pass unchanged.
- Public signature of `apply_adjustments(daily_df, corp_actions_df)` unchanged.
- Output URI, file layout unchanged.

## Phases

| # | Phase | Status |
|---|---|---|
| 01 | Vectorize adjustments + tests + deploy | Not started |

→ [phase-01-vectorize-adjustments.md](phase-01-vectorize-adjustments.md)

## Key Dependencies

- polars ≥ 0.20 (already pinned via `uv.lock`).
- `curate` Cloud Build image must rebuild post-merge.
- GCS raw URI `gs://vn-market-lake-prod/raw/daily_ohlcv/` for end-to-end smoke.
- Workflow `daily-ohlcv-refresh` to rebuild BQ native table after curate succeeds.

## Success

- Curate job for full universe completes well under 30 min (target < 5 min).
- `vnmarket.daily_ohlcv_native` last bar = 2026-05-28 after deploy + manual run.
- Daily schedule succeeds next 16:30 ICT cycle.
