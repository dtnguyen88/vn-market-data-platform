# Onboarding

> **Status:** Skeleton. Full content delivered in Phase 13 (Hardening). For now, the [Quickstart in README.md](../README.md#quickstart-for-local-dev) is the operative reference.

## Goal

A teammate with a fresh laptop should reach "I can read VN30 daily from the SDK" in under 30 minutes.

## Prerequisites (to be expanded)

- macOS / Linux / WSL2
- `gcloud` CLI installed and a Google account with access to the `vn-market-platform-staging` project
- `uv` >= 0.4
- `terraform` >= 1.7
- Git access to this repo

## Quickstart pointer

Use the [README quickstart](../README.md#quickstart-for-local-dev) until Phase 13 expands this doc.

## Sections to be filled in Phase 13

1. Laptop setup (gcloud, uv, terraform, ADC)
2. First clone + `uv sync --all-extras` + `pytest -m unit`
3. First Terraform `init` against staging
4. First SQL query against BigQuery
5. First notebook run via `notebooks/00-quickstart.ipynb`
6. Common gotchas
