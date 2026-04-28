#!/usr/bin/env bash
# Idempotently bring a fresh GCP project to "Terraform-ready" state.
# Usage: ./scripts/bootstrap-gcp-project.sh PROJECT_ID BILLING_ACCOUNT_ID ENV
# Example: ./scripts/bootstrap-gcp-project.sh vn-market-platform-staging 0X0X0X-0X0X0X-0X0X0X staging

set -euo pipefail

PROJECT_ID="${1:?project_id required}"
BILLING_ACCOUNT="${2:?billing_account_id required}"
ENV="${3:?env (staging|prod|test) required}"
REGION="asia-southeast1"

if [[ ! "${ENV}" =~ ^(staging|prod|test)$ ]]; then
  echo "ERROR: env must be one of: staging, prod, test (got: ${ENV})" >&2
  exit 1
fi

echo "==> Bootstrapping GCP project: ${PROJECT_ID} (env=${ENV})"

# 1. Create project if not exists
if ! gcloud projects describe "${PROJECT_ID}" &>/dev/null; then
  echo "==> Creating project ${PROJECT_ID}..."
  gcloud projects create "${PROJECT_ID}" --name="VN Market Platform ${ENV}"
fi

# 2. Link billing (idempotent: skip if already linked to the same account)
echo "==> Checking billing link..."
CURRENT_BILLING=$(gcloud billing projects describe "${PROJECT_ID}" --format='value(billingAccountName)' 2>/dev/null || echo "")
EXPECTED_BILLING="billingAccounts/${BILLING_ACCOUNT}"
if [[ "${CURRENT_BILLING}" != "${EXPECTED_BILLING}" ]]; then
  echo "==> Linking billing account ${BILLING_ACCOUNT}..."
  gcloud billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT}"
else
  echo "==> Billing already linked to ${BILLING_ACCOUNT}, skipping."
fi

# 3. Set project + region defaults
gcloud config set project "${PROJECT_ID}"
gcloud config set compute/region "${REGION}"

# 4. Enable required APIs (split into <=20-API batches per gcloud limit)
echo "==> Enabling APIs (batch 1/2)..."
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  serviceusage.googleapis.com \
  cloudbilling.googleapis.com \
  storage.googleapis.com \
  storage-api.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  workflows.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  bigqueryconnection.googleapis.com \
  bigquerystorage.googleapis.com

echo "==> Enabling APIs (batch 2/2)..."
gcloud services enable \
  secretmanager.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  firestore.googleapis.com

# 5. Create Terraform state bucket
TF_STATE_BUCKET="vn-mkt-tf-state-${ENV}"
if ! gsutil ls -b "gs://${TF_STATE_BUCKET}" &>/dev/null; then
  echo "==> Creating Terraform state bucket gs://${TF_STATE_BUCKET}..."
  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" -b on "gs://${TF_STATE_BUCKET}"
  gsutil versioning set on "gs://${TF_STATE_BUCKET}"
fi

# 6. Create terraform-sa
TF_SA="terraform-sa@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${TF_SA}" &>/dev/null; then
  echo "==> Creating terraform-sa..."
  gcloud iam service-accounts create terraform-sa \
    --display-name="Terraform IaC Service Account"
fi

# 7. Grant terraform-sa project owner (sufficient for IaC; tighten in Phase 11)
# roles/owner already supersedes roles/iam.securityAdmin and roles/storage.admin,
# so we don't grant those redundantly.
echo "==> Granting roles/owner to terraform-sa..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${TF_SA}" \
  --role="roles/owner" \
  --condition=None \
  --quiet

echo "==> Bootstrap complete."
echo "==> Next: cd infra/envs/${ENV} && terraform init && terraform plan"
