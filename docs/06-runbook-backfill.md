# Backfill Runbook

Run a historical backfill. Heavy operation; coordinate with team.

## Pre-flight

1. Confirm Phase 01-11 fully deployed.
2. Ensure target reference snapshot is fresh (`gcloud run jobs execute batch-ingester-reference`).
3. Check budget headroom (`gcloud run jobs execute cost-report --args=--mode=monthly`).

## Trigger

```bash
./scripts/run-backfill.sh staging 2021-01-01 2026-04-25 10 daily,fundamentals,corp_actions,reference
```

This launches `backfill` Cloud Run Job with 10 parallel tasks. Each task takes a date-range slice.

## Monitor

```bash
# List recent executions
gcloud run jobs executions list --job=backfill --region=asia-southeast1 \
  --project=vn-market-platform-staging

# Tail logs of specific execution
gcloud logging tail "resource.type=cloud_run_job AND resource.labels.job_name=backfill" \
  --project=vn-market-platform-staging
```

## Verify

```bash
# Spot-check daily for known event (COVID drop March 2020 vs our backfill range start)
bq query --use_legacy_sql=false \
  "SELECT MIN(date) AS min_d, MAX(date) AS max_d, COUNT(*) AS rows
   FROM \`vn-market-platform-staging.vnmarket.daily_ohlcv\`"

# Run data-quality validators
gcloud run jobs execute data-quality --region=asia-southeast1
```

## Troubleshooting

- **Task fails on rate-limit:** vnstock sources throttle. Reduce parallelism (`./scripts/run-backfill.sh ... 4 ...`).
- **Permanent gap recorded:** expected for ticks/L2 outside SSI's historical range (~12mo). Confirm via `gsutil cat gs://vn-market-lake-staging/_ops/permanent-gaps/ticks.jsonl`.
- **Memory OOM:** raise `memory` in `module.backfill_job` and `terraform apply`.
