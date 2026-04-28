# WIF Setup (one-shot per environment)

Run AFTER the initial bootstrap script + env apply, BEFORE GitHub Actions can deploy.

## Steps

```bash
cd infra/wif

# Staging
terraform init -backend=false
terraform apply \
  -var="project_id=vn-market-platform-staging" \
  -var="github_repo=ducthong/vn-market-data-platform" \
  -var="env=staging"

# Capture the two outputs and add to GitHub repo secrets:
#   WIF_PROVIDER_STAGING = wif_provider_resource
#   WIF_SA_STAGING       = cicd_sa_email

# Repeat for prod:
terraform apply \
  -var="project_id=vn-market-platform-prod" \
  -var="github_repo=ducthong/vn-market-data-platform" \
  -var="env=prod"
```

State is local (no remote backend). Re-running is idempotent.
