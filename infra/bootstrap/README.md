# Bootstrap Terraform Stack

One-shot Terraform setup. Run **once per environment** after `scripts/bootstrap-gcp-project.sh` succeeds.

## Usage

```bash
cd infra/bootstrap

# Staging
terraform init
terraform apply -var="project_id=vn-market-platform-staging" -var="env=staging"

# Prod (separate workspace or directory copy — local state is per-invocation)
terraform apply -var="project_id=vn-market-platform-prod" -var="env=prod"
```

## What it creates

- Default Firestore (Native mode) for telegram-alerter dedup state
- Artifact Registry Docker repo `vn-market` in `asia-southeast1`

## State

Local state — these resources are stable and rarely change. The bootstrap stack does **not** use the env's remote GCS backend (that bucket is created by the shell script *before* any Terraform runs). The local `terraform.tfstate` is gitignored; back it up out-of-band if you care about preserving import state. Re-running `terraform apply` is safe — both resources are identifiable by stable names.
