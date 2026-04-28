#!/usr/bin/env bash
# Build + push all 12 service images via Cloud Build.
# Usage: ./scripts/build-and-push.sh ENV
set -euo pipefail

ENV="${1:?env required (staging|prod|test)}"
if [[ ! "${ENV}" =~ ^(staging|prod|test)$ ]]; then
  echo "ERROR: env must be one of: staging, prod, test" >&2
  exit 1
fi

PROJECT_ID="vn-market-platform-${ENV}"
SERVICES=(publisher writers batch-eod batch-reference curate alerter research-app
          ops-cost-report ops-dlq-drain ops-dlq-replay ops-coverage-check ops-data-quality)

for svc in "${SERVICES[@]}"; do
  echo "==> building ${svc}..."
  gcloud builds submit \
    --project="${PROJECT_ID}" \
    --config="cloudbuild/${svc}.cloudbuild.yaml" \
    --substitutions=SHORT_SHA="$(git rev-parse --short HEAD)" \
    .
done

echo "==> all builds complete"
