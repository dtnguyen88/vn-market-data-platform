#!/usr/bin/env bash
# Apply BQ view DDLs in sql/views/ + (placeholder) refresh any registered MVs.
#
# Usage: ./scripts/refresh-mvs.sh ENV
# Example: ./scripts/refresh-mvs.sh staging
#
# DDLs use Jinja-style placeholders {{ project_id }} (sqlfluff-compat); script
# substitutes before piping to bq query.
#
# v1 note: all views are regular CREATE OR REPLACE VIEW — re-applying the DDL is
# the "refresh." MV refresh calls are stubbed but no MVs registered yet.

set -euo pipefail

ENV="${1:?env required (staging|prod|test)}"

if [[ ! "${ENV}" =~ ^(staging|prod|test)$ ]]; then
  echo "ERROR: env must be one of: staging, prod, test (got: ${ENV})" >&2
  exit 1
fi

PROJECT_ID="vn-market-platform-${ENV}"
VIEW_DIR="$(cd "$(dirname "$0")/.." && pwd)/sql/views"

if [[ ! -d "${VIEW_DIR}" ]]; then
  echo "ERROR: view dir not found: ${VIEW_DIR}" >&2
  exit 1
fi

echo "==> Applying VIEW DDLs to ${PROJECT_ID}..."

shopt -s nullglob
files=("${VIEW_DIR}"/*.sql)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "  (no .sql files; nothing to do)"
else
  for f in "${files[@]}"; do
    echo "  - $(basename "$f")"
    sed -e "s/{{ project_id }}/${PROJECT_ID}/g" \
        -e "s/{{ env }}/${ENV}/g" "$f" \
      | bq query --project_id="${PROJECT_ID}" --location=asia-southeast1 \
                  --use_legacy_sql=false --format=none
  done
fi

# v2: refresh registered materialized views.
# When views migrate to MATERIALIZED VIEW, list their fully-qualified names here.
MVS=()
if [[ ${#MVS[@]} -gt 0 ]]; then
  echo "==> Refreshing materialized views..."
  for mv in "${MVS[@]}"; do
    echo "  - ${mv}"
    bq query --project_id="${PROJECT_ID}" --location=asia-southeast1 \
             --use_legacy_sql=false --format=none \
             "CALL BQ.REFRESH_MATERIALIZED_VIEW('${mv}')"
  done
fi

echo "==> Done. Verify with: bq ls ${PROJECT_ID}:vnmarket"
