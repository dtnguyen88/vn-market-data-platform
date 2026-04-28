# Orchestration Operations Guide

## Workflow inventory

| Workflow | Schedule (ICT) | Purpose |
|---|---|---|
| eod-pipeline | 16:00 weekdays | Batch EOD + parallel curate |
| intraday-coverage-check | every 5 min, 9-15 weekdays | Ingest receipt audit |
| reference-refresh | 06:00 weekdays | Ticker + futures master |
| curate-fallback | 17:00 weekdays | Idempotent curate retry |
| calendar-refresh-yearly | Dec 1 09:00 | Verify next year's calendar JSON |
| monthly-cost-report | 1st of month 09:00 | Cloud Billing summary |

## Manual trigger

```bash
gcloud workflows run eod-pipeline \
  --project=vn-market-platform-staging \
  --location=asia-southeast1 \
  --data='{"target_date":"2024-01-15","env":"staging"}'
```

## Inspecting executions

```bash
gcloud workflows executions list \
  --workflow=eod-pipeline \
  --project=vn-market-platform-staging \
  --location=asia-southeast1
```

## Troubleshooting

- **Step fails on Cloud Run Job not found:** verify image exists in Artifact Registry; redeploy via Cloud Build.
- **Workflow timeout:** default 1h; for backfill or large EOD, raise via `timeout: "5400s"` on the step.
- **Calendar fetch fails:** workflow's GCS read needs `roles/storage.objectViewer` on `vn-market-lake-{env}` for `workflows-sa`.
