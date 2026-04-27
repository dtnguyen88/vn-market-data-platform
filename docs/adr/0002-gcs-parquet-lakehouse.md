# ADR-0002 — GCS Parquet lakehouse (not pure BigQuery, not ClickHouse Cloud)

**Date:** 2026-04-25
**Status:** Accepted
**Context:** [01-architecture.md §1, §2](../01-architecture.md)

## Decision

Adopt a GCS-as-source-of-truth lakehouse pattern: Parquet files on GCS, exposed to SQL via BigQuery BigLake external tables, read directly from notebooks via Polars/DuckDB.

## Context

Three storage architectures were considered for a Vietnam market data platform:

- **A. Pure BigQuery** — all data lands in BQ native tables, queried via BQ SQL.
- **B. ClickHouse Cloud + BigQuery hybrid** — CH for ticks/quotes, BQ for daily/fundamentals.
- **C. GCS Parquet lakehouse + BQ BigLake** (chosen).

Researcher workflow was confirmed as: Python notebooks (Polars) for exploration + BQ SQL for heavy aggregations + Parquet pulls for backtest input.

Coverage scope is full universe (~1,600 equities) × tick + L1 + L2 + indices + futures, 5-year historical backfill. Budget ceiling $300/mo GCP. Estimated 5y data volume ~5.5 TB.

## Considered alternatives

### A. Pure BigQuery
- Pros: simplest, single SQL surface, zero ops
- Cons: BQ active-storage at $0.02/GB plus per-query scan costs; L2 quote queries scanning gigabytes accumulate fast; researcher Polars workflow needs a separate "export to Parquet" step every time
- Est cost: $60–150/mo

### B. ClickHouse Cloud + BigQuery hybrid
- Pros: best tick query latency; closest to existing `Data_Platform/` self-hosted mental model
- Cons: ClickHouse Cloud minimum dev tier ~$60/mo eats 20% of budget before any usage; two storage systems and two query languages to maintain; Cloud Composer (~$30/mo) needed to orchestrate cross-system loads
- Est cost: $150–250/mo (brushes ceiling)

### C. GCS Parquet lakehouse + BigQuery BigLake (chosen)
- Pros: cheapest at scale; researcher Polars/DuckDB workflow IS this natively (no export step); vendor-neutral (Parquet portable to any future stack); lakehouse is the modern standard
- Cons: BigLake queries slightly slower than native BQ; tick freshness limited by writer flush cadence (60s)
- Est cost: $30–80/mo at v1, ~$200–235/mo at year-5 steady state

## Why C wins

1. **Native fit for researcher workflow.** D = "notebooks + BQ SQL + Parquet pulls." Approach C makes the storage layer literally Parquet on object storage — Polars reads it directly via `pyarrow.dataset` with no transformation step. No "export to parquet for backtest" pipeline needed.
2. **Cost discipline.** Comfortably in lower half of $300 budget at year-5 steady state, with documented levers (Coldline lifecycle for old L2, etc.) to push lower if needed.
3. **Forward-compatibility.** If tick latency becomes critical later, ClickHouse can be added as a *secondary* sink on existing Pub/Sub topics. The Parquet lake stays as the durable source of truth. No rewrite required.
4. **Vendor neutrality.** Parquet on object storage is portable to any future query engine (Iceberg, Snowflake, Databricks, Trino, raw DuckDB). BigQuery is great but not the only option, and we shouldn't lock in.
5. **BQ on-demand for SQL.** BigLake gives us BQ SQL surface without paying for BQ storage. Best of both: queries when we want SQL, files when we want raw access.

## Consequences

- GCS bucket layout becomes load-bearing — partitioning scheme ([§2.1](../01-architecture.md#21-gcs-bucket-structure-medallion--bronze-silver)) must be designed up-front for query patterns.
- Curated layer is a real artifact (built nightly), not just a BQ view. Adds `curate-{stream}` Cloud Run Jobs to v1 scope.
- BigLake external tables don't support DML (INSERT/UPDATE/DELETE) — all writes go through GCS. This is fine for analytics workload; would block OLTP use cases (we don't have any).
- Materialized views (`v_top_of_book`, `v_session_vwap`, `v_daily_factors`) compensate for BigLake's slightly slower scan vs native BQ.
- The `vnmarket` Python SDK gains importance as the canonical read-path API — without it, researchers write boilerplate `gs://` glue.

## Reversal

Migrating from C → A (lift to native BQ) is straightforward via `LOAD DATA OVERWRITE ... FROM 'gs://.../*.parquet'`. Reverse direction (BQ native → GCS Parquet) is also doable via BQ export.

Migrating to C → B (add CH) is additive, not a replacement: CH becomes a second sink fed from Pub/Sub. Lake stays.

The decision is reversible in any direction at relatively low cost.
