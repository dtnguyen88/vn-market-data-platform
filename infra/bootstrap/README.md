# Bootstrap Terraform Stack

One-shot Terraform setup. Run **once per environment** after `scripts/bootstrap-gcp-project.sh` succeeds.

## Usage

```bash
cd infra/bootstrap
terraform init
terraform apply -var="project_id=vn-market-platform-staging" -var="env=staging"
```

## What it creates

- Default Firestore (Native mode) for telegram-alerter dedup state
- Artifact Registry Docker repo `vn-market` in `asia-southeast1`

## State

Local state — these resources are stable and rarely change. (Do NOT use the env's remote backend; that bucket is created by the shell script before any Terraform runs.)
