# Incident Response Runbook

## Triage flow

1. **Receive Telegram alert** → check severity
2. **Click [Logs] link** in alert → Cloud Logging filtered by alert_name
3. **Identify failing service** → `gcloud run services list` and check error revision
4. **Quick fixes** below

## Common alerts → actions

### `publisher heartbeat absent >90s`

Cause: shard's WebSocket disconnected or container crashed.

```bash
# Inspect last logs
gcloud run services logs read realtime-publisher-shard-0 --limit=100

# Force redeploy (picks up latest image)
gcloud run services update realtime-publisher-shard-0 --region=asia-southeast1 --tag=fresh
```

### `Pub/Sub topic publish rate = 0 >120s`

Cause: all 4 publisher shards stalled, or Pub/Sub-side issue.

```bash
# Check all 4 shards
for s in 0 1 2 3; do
  gcloud run services describe realtime-publisher-shard-$s --region=asia-southeast1 \
    --format='value(status.conditions[0].message)'
done

# If only some shards down, restart specific shard. If all 4: check SSI auth (secret rotation?)
gcloud secrets versions access latest --secret=ssi-fc-username  # confirm not empty
```

### `subscription oldest_unacked_message_age >180s`

Cause: writer service crashed or processing too slow.

```bash
gcloud run services logs read parquet-writer-ticks --limit=50

# If slow processing: scale up
gcloud run services update parquet-writer-ticks --max-instances=10 --region=asia-southeast1

# If crash loop: redeploy
gcloud run services update parquet-writer-ticks --region=asia-southeast1
```

### `dlq drain non-zero count`

Cause: messages failed delivery 5x → forwarded to DLQ.

```bash
# Inspect DLQ export
gsutil ls gs://vn-market-lake-staging/_ops/dlq-export/

# After fixing root cause, replay
gcloud run jobs execute dlq-replay \
  --args=--export-uri=gs://vn-market-lake-staging/_ops/dlq-export/market-ticks/run=...,--target-topic=market-ticks
```

### `data quality validator findings`

Run weekly. Findings written to `_ops/data-quality-issues/`. Investigate but no immediate ops action.

## Post-incident

1. Document timeline + root cause in `plans/reports/incident-{date}-{slug}.md`
2. Add new alert if existing alerting missed the event
3. Update this runbook with the new fix recipe
