#!/usr/bin/env bash
# Force a Cloud Run revision rollout for all services after a fresh image push.
# Useful when terraform apply doesn't trigger a redeploy (image tag unchanged).
# Usage: ./scripts/deploy-services.sh ENV
set -euo pipefail

ENV="${1:?env required}"
PROJECT_ID="vn-market-platform-${ENV}"
REGION="asia-southeast1"

SERVICES=(realtime-publisher-shard-0 realtime-publisher-shard-1
          realtime-publisher-shard-2 realtime-publisher-shard-3
          parquet-writer-ticks parquet-writer-quotes-l1
          parquet-writer-quotes-l2 parquet-writer-indices
          telegram-alerter research-app)

for svc in "${SERVICES[@]}"; do
  echo "==> redeploying ${svc}..."
  gcloud run services update "${svc}" --project="${PROJECT_ID}" --region="${REGION}" --tag=fresh
done
