#!/usr/bin/env bash
# Apply BigQuery BigLake external table DDLs.
# Usage: ./scripts/apply-bq-schemas.sh ENV
# Example: ./scripts/apply-bq-schemas.sh staging
#
# DDL files in sql/schemas/ use Jinja-style placeholders {{ project_id }} and
# {{ env }} so they lint cleanly with sqlfluff. This script substitutes both
# before piping to bq query.

set -euo pipefail

ENV="${1:?env required (staging|prod|test)}"

if [[ ! "${ENV}" =~ ^(staging|prod|test)$ ]]; then
  echo "ERROR: env must be one of: staging, prod, test (got: ${ENV})" >&2
  exit 1
fi

PROJECT_ID="vn-market-platform-${ENV}"
SCHEMA_DIR="$(cd "$(dirname "$0")/.." && pwd)/sql/schemas"

if [[ ! -d "${SCHEMA_DIR}" ]]; then
  echo "ERROR: schema dir not found: ${SCHEMA_DIR}" >&2
  exit 1
fi

echo "==> Applying BigQuery DDLs to ${PROJECT_ID}..."

shopt -s nullglob
files=("${SCHEMA_DIR}"/*.sql)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "ERROR: no .sql files in ${SCHEMA_DIR}" >&2
  exit 1
fi

for f in "${files[@]}"; do
  echo "  - $(basename "$f")"
  sed -e "s/{{ project_id }}/${PROJECT_ID}/g" \
      -e "s/{{ env }}/${ENV}/g" "$f" \
    | bq query --project_id="${PROJECT_ID}" --location=asia-southeast1 \
                --use_legacy_sql=false --format=none
done

echo "==> Done. Verify with: bq ls ${PROJECT_ID}:vnmarket"
