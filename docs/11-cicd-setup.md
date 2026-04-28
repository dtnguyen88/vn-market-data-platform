# CI/CD Setup (Phase 11)

## Prerequisites

- GitHub repo created and code pushed
- Phase 01 + Phase 02 deployed in staging (and prod if applicable)
- gcloud auth + ADC configured

## Setup checklist

1. **WIF (one-time per env):**
   - `cd infra/wif && terraform apply ...` (see infra/wif/README.md)
   - Capture outputs: `wif_provider_resource`, `cicd_sa_email`

2. **GitHub repo secrets** (Settings → Secrets and variables → Actions):
   - `WIF_PROVIDER_STAGING` (= wif_provider_resource for staging)
   - `WIF_SA_STAGING`       (= cicd_sa_email for staging)
   - `WIF_PROVIDER_PROD`    (= wif_provider_resource for prod)
   - `WIF_SA_PROD`          (= cicd_sa_email for prod)
   - `WIF_PROVIDER_TEST`    (for integration tests against test project)
   - `WIF_SA_TEST`
   - `GCP_PROJECT_ID_TEST`  (e.g., `vn-market-platform-test`)

3. **GitHub Environment** (for prod approval):
   - Settings → Environments → New environment "production"
   - Required reviewers: yourself
   - Used by `deploy-prod.yml` to gate apply on manual approval

4. **Branch protection** (Settings → Branches → main):
   - Require PR review: 1 approver (or self for solo dev)
   - Require status checks: `unit`, `integration`
   - Require linear history (optional)

## Workflow triggers

| Workflow | Trigger | Auth |
|---|---|---|
| unit | PR + push main | none |
| integration | PR + push main | WIF_TEST |
| contract | nightly cron + manual | none (read-only public sources) |
| deploy-staging | push main | WIF_STAGING |
| deploy-prod | tag v*.*.* | WIF_PROD + manual approval |

## Per-PR cost

- unit: ~3 min runtime (free for public/personal repos)
- integration: ~15 min, hits test GCP project (~$0.05/run)
- Total per PR: under $0.10

## Rollback procedure

```bash
# Re-tag the previous good version (e.g., v0.1.0)
git tag -f v0.1.1 v0.1.0
git push origin v0.1.1 --force
# This triggers deploy-prod.yml which redeploys with the older code+image
```
