#!/usr/bin/env bash
# Trigger the backfill Cloud Run Job with a specific date range.
# Usage: ./scripts/run-backfill.sh ENV START END [TASKS] [STREAMS]
# NOTE: TASKS=1 recommended for vnstock community (20 req/min hard limit per IP).
set -euo pipefail
ENV="${1:?env required}"
START="${2:?start YYYY-MM-DD required}"
END="${3:?end YYYY-MM-DD required}"
TASKS="${4:-1}"
STREAMS="${5:-daily,fundamentals,corp_actions,reference}"

PROJECT_ID="vn-market-platform-${ENV}"
# ^@^ separator so commas inside --streams aren't split as separate args.
gcloud run jobs execute backfill \
  --project="${PROJECT_ID}" --region=asia-southeast1 \
  --tasks="${TASKS}" \
  --args="^@^--start=${START}@--end=${END}@--streams=${STREAMS}"
