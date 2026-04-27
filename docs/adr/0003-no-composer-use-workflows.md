# ADR-0003 — Cloud Workflows, not Cloud Composer / Airflow

**Date:** 2026-04-25
**Status:** Accepted
**Context:** [01-architecture.md §4](../01-architecture.md)

## Decision

Use Cloud Scheduler + Cloud Workflows + Cloud Run Jobs for all batch orchestration. Do not deploy Cloud Composer (managed Airflow) or run a self-hosted Airflow.

## Context

The existing `Data_Platform/` self-hosted stack uses Airflow for orchestration with several DAGs (`batch_ingestion_dag.py`, `cdc_monitor_dag.py`, `data_quality_dag.py`, `transform_pipeline_dag.py`). Migrating those mental models to GCP, the natural first instinct is Cloud Composer.

The new platform has 6 batch DAGs with ≤10 steps each, mostly linear with one parallel fan-out (the curate stage in `eod-pipeline`). No cross-DAG dependencies. No backfill UI requirements. Solo operator.

## Considered alternatives

### A. Cloud Composer (managed Airflow)
- Pros: full Airflow feature set (UI, sensors, XCom, cross-DAG deps, plugin ecosystem); same mental model as existing `Data_Platform/`
- Cons: minimum tier ~$30/mo even idle; cluster bootstrap takes 25+ min; operational surface (GKE under the hood) inappropriate at this scale
- Est cost: $30–60/mo

### B. Self-hosted Airflow on Cloud Run / GKE
- Pros: free-ish, total control
- Cons: ops burden; need a metadata DB; same complexity reasons Composer is overkill
- Est cost: $20–40/mo + significant ops time

### C. Cloud Scheduler + Cloud Workflows + Cloud Run Jobs (chosen)
- Pros: serverless (no idle cost); YAML workflow definitions; native Cloud Run Jobs integration; built-in retries, error handlers, parallel branches; integrates with Cloud Logging and Monitoring out of the box; visualizable DAG in Workflows console
- Cons: less feature-rich than Airflow (no UI for backfills, no plugin ecosystem, weaker sensors)
- Est cost: <$1/mo for our ~3,000 steps/mo

### D. GitHub Actions cron triggering Cloud Run Jobs directly
- Pros: simplest, no GCP-side orchestration
- Cons: no intra-DAG dependencies, no parallel branches with join, no retries beyond GH Actions defaults, depends on GitHub uptime
- Not viable for the EOD pipeline structure.

## Why C wins

1. **Cost.** Composer's $30+/mo idle cost is 10% of our budget for capabilities we don't use. Workflows is pennies.
2. **Right-sized capability.** Our DAGs are simple: linear with one fan-out. Workflows YAML expresses this in <50 lines per workflow. Airflow's full feature set is overkill.
3. **Native serverless integration.** Workflows triggers Cloud Run Jobs directly via the API. No worker pool, no Celery, no executor configs.
4. **Operational simplicity.** No cluster, no metadata DB, no plugin compat headaches, no Airflow version upgrades. Deploys are `gcloud workflows deploy` from CI.
5. **Observability included.** Step-level success/failure, duration, logs all surface in Cloud Logging + Workflows console without configuration.

## Consequences

- Trading-calendar-aware scheduling pattern: every workflow's first step is `check_trading_day()` (see [§4.4](../01-architecture.md#44-trading-calendar)). Cron filters at scheduler level + holiday filters at workflow level = two-layer skip.
- No Airflow-style plugin reuse from `Data_Platform/dags/` — DAG logic must be re-expressed in Workflows YAML + Cloud Run Job code. Acceptable cost given ~6 simple DAGs.
- No first-class backfill UI. Backfill is invoked manually via `gcloud run jobs execute backfill ...` (acceptable; documented in `docs/06-runbook-backfill.md`).
- Cross-DAG dependencies (if ever needed) require Pub/Sub messaging between workflows. None planned.
- Telegram-driven operability replaces Airflow's UI for monitoring (see [§6](../01-architecture.md#6-alerting--observability)).

## When to revisit

Revisit if any of the following becomes true:
- DAG count exceeds ~20 with cross-DAG dependencies
- Need a backfill UI for a non-engineer operator
- Need the Airflow plugin ecosystem (sensors for external systems we don't own)
- Hire a data engineering team that's already fluent in Airflow

None of these are anticipated for v1 or v2.

## Reversal

Migrating to Composer would require: re-expressing 6 workflow YAMLs as Airflow DAGs, deploying Composer environment, re-pointing schedulers. Estimated 1–2 weeks of work. Not blocked by current design.
