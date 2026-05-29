# Phase 01 — Vectorize `apply_adjustments`

## Context Links

- Source: `src/curate/adjustments.py` (the loop)
- Caller: `src/curate/streams/daily_ohlcv.py`
- Tests: `tests/unit/test_adjustments.py` (8 existing cases)
- Build: `cloudbuild/curate.cloudbuild.yaml`
- Workflow: `infra/workflows/daily-ohlcv-refresh.yaml`
- Dedup helper: `src/curate/dedup.py` (untouched)

## Overview

- **Priority:** P0 (lake stale 30 days, blocking research + dashboards).
- **Status:** Not started.
- **Description:** Replace per-symbol Python `for`-loop + `map_elements` UDF in `apply_adjustments` with polars-native group/aggregate/join. Preserve semantics + signature. Add perf-budget test + small end-to-end fixture test.

## Key Insights

- Corp actions sparse: ~3–10 rows/symbol/year → join blows up to manageable size, not 3M × 3M.
- Factor per `(symbol, ex_date)` row already computed via `map_elements` over a small frame — that path is fine (rows in `corp_actions_df` typically << 100k). Keep it.
- The killer is the `daily_df["date"].map_elements(lambda d: _cumulative_factor(...))` over millions of daily rows. THIS is what must go.
- Replacement: for each `(symbol, date)` daily row, factor product = product of `factor` where same `symbol` AND `ex_date > date`. Implement as join + group_by + product aggregation.

## Requirements

**Functional**
- `apply_adjustments(daily_df, corp_actions_df) -> pl.DataFrame` returns same schema as before: daily columns + `adj_close: Int64`.
- Empty `corp_actions_df` → `adj_close = close` (existing test).
- Split / cash dividend / stock dividend / rights semantics unchanged (existing tests).
- Symbols absent from `corp_actions_df` → `adj_close = close`.
- Sorted output not required (existing tests `.sort("date")` themselves before asserting).

**Non-functional**
- 50k daily rows × 50 corp actions: < 5 s on dev laptop (perf-budget test).
- Full universe (~3M daily × ~5k actions): completes within Cloud Run job 30-min cap with margin (target < 5 min for adjustments step).
- No new dependencies.

## Architecture

```
daily_df                            corp_actions_df
   │                                       │
   │ (unchanged)                           │ sort + join_asof for close_prev
   │                                       │ + map_elements over SMALL frame
   │                                       │ → factors: (symbol, ex_date, factor)
   │                                       │
   └──────────────┬────────────────────────┘
                  │ join on symbol (many-to-many)
                  │ filter ex_date > date
                  │ group_by(symbol, date) → product(factor)
                  ▼
        factor_per_day: (symbol, date, factor_prod)
                  │
                  │ left join back onto daily_df
                  │ fill null factor_prod with 1.0
                  ▼
        adj_close = close.cast(Float64) * factor_prod  → cast Int64
```

## Related Code Files

**Modify**
- `src/curate/adjustments.py` — replace per-symbol loop (lines 93–113) with vectorized join+group_by+product. Keep factor-construction block (62–89) as-is.
- `tests/unit/test_adjustments.py` — add 2 tests: perf-budget + multi-symbol multi-action.

**Create**
- `tests/integration/test_curate_daily_ohlcv_e2e.py` — small end-to-end test from a recorded fixture (tiny Parquet committed under `tests/fixtures/curate/`).

**Fixtures**
- `tests/fixtures/curate/daily_small.parquet` — ~5 symbols × ~60 days.
- `tests/fixtures/curate/corp_actions_small.parquet` — ~5 actions covering split + cash + stock + no-action symbol.

**Delete:** none.

## Implementation Steps

1. **Refactor `apply_adjustments`** in `src/curate/adjustments.py`:
   - Keep the empty-`corp_actions_df` early-return (line 58–59) unchanged.
   - Keep factor construction (lines 62–89) unchanged — it operates on the small actions frame.
   - Replace lines 91–113 with:
     ```python
     # Cross-join factors onto daily rows by symbol, keep only future actions.
     joined = daily_df.join(factors, on="symbol", how="left")
     # Future-action mask: factor applies if ex_date > date.
     applicable = joined.filter(pl.col("ex_date").is_not_null() & (pl.col("ex_date") > pl.col("date")))
     factor_per_day = applicable.group_by(["symbol", "date"]).agg(
         pl.col("factor").product().alias("factor_prod")
     )
     out = daily_df.join(factor_per_day, on=["symbol", "date"], how="left").with_columns(
         pl.col("factor_prod").fill_null(1.0)
     )
     out = out.with_columns(
         adj_close=(pl.col("close").cast(pl.Float64) * pl.col("factor_prod")).cast(pl.Int64)
     ).drop("factor_prod")
     return out
     ```
   - Verify no leftover `_cumulative_factor` callers; delete the helper if unused.
2. **Run existing unit tests** — all 8 cases in `tests/unit/test_adjustments.py` must pass unchanged:
   `uv run pytest tests/unit/test_adjustments.py -v`
3. **Add multi-symbol multi-action test** to `tests/unit/test_adjustments.py`:
   - 3 symbols (VNM, FPT, HPG). VNM has split + cash. FPT has nothing. HPG has stock dividend.
   - Assert each symbol's adj_close independently.
4. **Add perf-budget test** to `tests/unit/test_adjustments.py`:
   - Synthesize 100 symbols × 500 days = 50k rows + ~300 actions.
   - `import time`; assert wall-time < 5.0 s.
   - Mark `@pytest.mark.unit` (runs in CI, cheap).
5. **Create fixtures** under `tests/fixtures/curate/`:
   - Use a one-off script (committed as `scripts/make_curate_fixtures.py` if convenient, otherwise inline in test) to write small Parquet files. ~5 symbols × ~60 trading days, plus 4 corp actions.
6. **Create `tests/integration/test_curate_daily_ohlcv_e2e.py`**:
   - Calls `curate_daily_ohlcv(raw_uri=fixture_daily, corp_actions_uri=fixture_actions, curated_uri=tmp_path/"out.parquet")`.
   - Reads output back, asserts row count = dedup input rows and `adj_close` non-null + non-zero.
   - Marks `@pytest.mark.integration` so it runs locally but is opt-in in CI.
7. **Run full test suite**: `uv run pytest -m "unit or integration" -v`.
8. **Local smoke vs recorded slice** (optional but recommended):
   - Run `uv run python -m curate --stream=daily-ohlcv --raw-uri=gs://vn-market-lake-prod/raw/daily_ohlcv/date=2026-05-28/ --corp-actions-uri=... --curated-uri=/tmp/out.parquet` (or whichever CLI shape ships).
   - Confirm runtime < 5 min, output non-empty.
9. **Commit + PR**: `fix(curate): vectorize daily-ohlcv adjustments to clear 30-min Cloud Run cap`.
10. **Deploy steps after merge**:
    1. Trigger Cloud Build for curate image:
       `gcloud builds submit --config cloudbuild/curate.cloudbuild.yaml --project vn-market-platform-prod .`
    2. Confirm `asia-southeast1-docker.pkg.dev/vn-market-platform-prod/vn-market/curate:latest` digest updated.
    3. Re-run curate job manually:
       `gcloud run jobs execute curate --region asia-southeast1 --project vn-market-platform-prod --args="--stream=daily-ohlcv"`
    4. Tail logs; confirm completion < 10 min and `rows_out > 0`.
    5. Trigger workflow:
       `gcloud workflows run daily-ohlcv-refresh --location asia-southeast1 --project vn-market-platform-prod --data='{"target_env":"prod"}'`
    6. Verify in BQ:
       `bq query --use_legacy_sql=false 'SELECT MAX(date) FROM vn-market-platform-prod.vnmarket.daily_ohlcv_native'` → expect 2026-05-28.
    7. Watch next 16:30 ICT scheduled run — must succeed.

## Todo List

- [ ] Refactor `apply_adjustments` (loop → polars join + group_by + product).
- [ ] Run existing `tests/unit/test_adjustments.py` — 8 cases pass.
- [ ] Add multi-symbol multi-action unit test.
- [ ] Add perf-budget unit test (50k rows < 5 s).
- [ ] Create `tests/fixtures/curate/` Parquet fixtures.
- [ ] Create `tests/integration/test_curate_daily_ohlcv_e2e.py`.
- [ ] `uv run pytest -m "unit or integration"` green.
- [ ] Manual GCS slice smoke (optional).
- [ ] Open PR; merge to main.
- [ ] Cloud Build curate image (prod).
- [ ] Manual curate job execute, confirm completion.
- [ ] Trigger `daily-ohlcv-refresh` workflow.
- [ ] BQ verification: `MAX(date) = 2026-05-28`.
- [ ] Observe next 16:30 ICT scheduled cycle.

## Success Criteria

- All existing + new unit tests pass.
- Perf-budget test < 5 s (CI dev laptop).
- E2E integration test green against fixture.
- After deploy: curate job runs < 10 min; `daily_ohlcv_native` MAX(date) = 2026-05-28.
- Next scheduled 16:30 ICT cycle succeeds.

## Risk Assessment

- **Many-to-many join blow-up**: factor frame typically ~5k rows, daily ~3M → joined frame ~tens of millions before filter. Polars handles this; if RAM-tight, group factors per-symbol to a list and use `pl.col("ex_date").is_in()`/array math. Mitigation: keep filter immediately after join; verify perf test passes at scale.
- **Subtle factor-prod semantics drift**: `group_by + product` on left-joined null rows could mis-aggregate. Mitigation: filter `ex_date.is_not_null() & (ex_date > date)` BEFORE group_by, then left-join back with `fill_null(1.0)`.
- **Int64 cast rounding**: existing tests already allow `abs(... - 909) <= 1`. Same cast path preserved.
- **Fixture brittleness**: keep fixtures tiny + deterministic; avoid network IO.

## Security Considerations

- No new secrets / IAM changes.
- Cloud Build + Cloud Run job continue to use existing `workflows-sa` / `curate-sa` — verified in prior commits.

## Next Steps

- Once stable, consider partitioning curated output by year for incremental writes (deferred — out of scope per KISS).
- Monitor `daily-ohlcv-refresh` job latency; if BQ MERGE becomes cheaper than CREATE OR REPLACE at 5×+ volume, revisit workflow.

## Unresolved Questions

- What's the exact CLI shape of `curate` for the manual smoke step? README mentions `python -m curate` but the Cloud Run job uses some entrypoint inside the Dockerfile — confirm during step 8 / step 10.3.
- Are `corp_actions` writes guaranteed to land before `daily_ohlcv` in the EOD pipeline? If not, an empty `corp_actions` frame ships and adj_close == close silently. Out of scope here but flag for follow-up.
- Should the perf-budget test live under `unit` or a separate `perf` mark? Default to `unit` for now; reclassify if it flakes on slow CI runners.
