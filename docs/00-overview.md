# 00 — Overview & Decisions

> **Spec:** VN Market Data Platform
> **Date:** 2026-04-25
> **Status:** Approved spec, pre-implementation
> **Companion:** [01-architecture.md](01-architecture.md), [adr/](adr/)

## Goal

Build a GCP-hosted data platform that captures Vietnam market data (equities, futures, indices) at full breadth and depth, makes it available to a quant researcher via SQL + Polars + dashboards, and self-monitors with Telegram alerts.

## Scope (v1)

| Asset class | Universe | Daily | Fundamentals | Intraday ticks | L1 quotes | L2 quotes (10 lvl) |
|---|---|:-:|:-:|:-:|:-:|:-:|
| Equities | All ~1,600 listed (HOSE + HNX + UPCoM) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Index futures (VN30F*) | VN30F1M, VN30F2M, VN30F1Q, VN30F2Q | ✅ | n/a | ✅ | ✅ | ✅ |
| Indices | All ~30+ (main + sector + thematic across HOSE/HNX/UPCoM) | ✅ | n/a | ✅ (intraday values) | n/a | n/a |

| Item | Decision |
|---|---|
| Historical backfill depth | 5 years |
| Region | `asia-southeast1` |
| Budget ceiling (GCP) | $300/mo |
| External cost | SSI FastConnect Data subscription (~$50–200/mo, separate) |
| Environments | `prod`, `staging`, `test` |

## Out of scope (v1)

- Bond futures (GB05F, GB10F)
- Real-time L2 for non-VN exchanges
- Cross-region replication
- Multi-tenant access (single user)
- Production-grade SCD Type 2 on tickers (snapshotted daily for v1)
- ML feature store (researcher rolls their own from curated layer)
- Trading execution / order management

## Top-level architecture (one-liner)

```
SSI FC WS ─┐
           │  Cloud Run publishers (4 shards) ──▶ Pub/Sub ──▶ Cloud Run writers (4) ──▶ GCS Parquet
vnstock ───┘                                                                              │
                                                                                           ▼
                                                                          BigQuery BigLake + Looker Studio
                                                                          + vnmarket SDK (Polars/DuckDB)
                                                                          + Streamlit on Cloud Run

Cloud Scheduler → Cloud Workflows → Cloud Run Jobs    (orchestration; trading-calendar aware)
Cloud Monitoring → Pub/Sub → telegram-alerter         (alerting)
```

Detail in [01-architecture.md](01-architecture.md).

## Key decisions log

| # | Decision | Alternative considered | Reason |
|---|---|---|---|
| 1 | Hybrid GCP-native, not lift-and-shift | (a) pure BigQuery, (b) port Docker stack to GKE | Best cost/UX for solo quant; keeps existing concepts where they fit |
| 2 | SSI FastConnect Data as primary source | DNSE (free), VPS, vnstock-only | User committed to pro tier; only path to L2 + full coverage |
| 3 | GCS Parquet + BigLake external tables | (a) native BigQuery for everything, (b) ClickHouse Cloud + BigQuery hybrid | Cheapest, matches researcher Polars/DuckDB workflow, vendor-neutral |
| 4 | Pub/Sub from day one (not "v2 if needed") | In-memory buffer in publisher | Durability + replay + decoupling far outweigh ~$8/mo cost. See [ADR-0001](adr/0001-pubsub-from-day-one.md) |
| 5 | Cloud Workflows + Scheduler (not Composer/Airflow) | Cloud Composer (managed Airflow) | Composer = $30+/mo minimum; Workflows is YAML and serverless. See [ADR-0003](adr/0003-no-composer-use-workflows.md) |
| 6 | 4-shard publisher (not single instance) | Single Cloud Run with one WS | At ~1,600 symbols × L2, single-instance bandwidth risk; sharding is static and simple |
| 7 | Always-on publishers (not scale-to-zero overnight) | Scale to 0 at 15:05, back at 08:35 | Saves $20/mo, costs cold-start risk + 2 extra workflows; not worth it in v1 |
| 8 | Realtime alerts via Cloud Monitoring (not 30-min poll) | Periodic gap-detection workflow | Native event-driven, fires in 60–120s vs 30 min |
| 9 | Telegram-only alert channel | Email / Slack / PagerDuty | Single channel = single source of truth; swap path documented |
| 10 | Bucket versioning ON (30d retention) | No versioning | ~10% storage cost; saves you from buggy curate runs |
| 11 | Curated layer rebuilt nightly (not streaming) | Streaming curate via Dataflow | Nightly is enough for research workload; Dataflow is operationally heavy |
| 12 | Hardcoded VN holiday JSON (yearly human-in-loop refresh) | Auto-scrape HOSE | Holiday changes by official decree mid-year happen; HITL is correct pattern |
| 13 | Single uv workspace, 7 Dockerfiles | Repo-per-service | Solo dev; monorepo wins on shared `vnmarket` SDK + ergonomics |
| 14 | 70% test coverage target, not gated | 90%+ gated | Pragmatic for solo dev; correctness comes from data-quality validators (8.6) |
| 15 | Single region asia-southeast1 | Multi-region | Cheaper; latency to SSI FC servers; revisit at v2 |

## Open questions / deferred to v2

- **L2 retention horizon** — keeping all 5 years is current plan. If query patterns show only 2y is used, lifecycle to delete saves ~$50/mo.
- **SCD Type 2 for `tickers`** — currently daily snapshot. Backtest accuracy on point-in-time joins may demand SCD2 later.
- **Live alerting on data quality** — currently weekly batch validators. Could push to event-driven if alpha research needs faster feedback.
- **ClickHouse as secondary tick sink** — if research workflow shifts toward microsecond-latency queries, add CH subscriber on existing Pub/Sub topics. Architecture supports it without disturbing v1.
- **SSI FastConnect subscription tier** — exact tier (and cost) to confirm at SSI signup. May influence message volume estimates and Pub/Sub cost.
- **Scale-to-zero overnight** — deferred per Decision 7; revisit if cost trends upward.

## Acceptance criteria for "v1 done"

1. All 4 realtime streams ingest cleanly during a full trading session with zero EOD gaps.
2. EOD pipeline completes by 17:00 ICT trading days, posts Telegram summary.
3. Researcher can run `00-quickstart.ipynb` end-to-end from a fresh laptop with one `gcloud auth` command.
4. Looker Studio "Market Overview" dashboard renders with current-day data.
5. 5-year backfill of daily + fundamentals complete and queryable.
6. Telegram receives a critical alert within 2 minutes of a forced publisher kill (chaos test).
7. Monthly cost report fires on the 1st with prior-month total under $300.

## Pointers

- Full architecture, components, data model, orchestration, alerting, testing, repo layout, cost: **[01-architecture.md](01-architecture.md)**
- ADRs: **[adr/0001](adr/0001-pubsub-from-day-one.md)**, **[adr/0002](adr/0002-gcs-parquet-lakehouse.md)**, **[adr/0003](adr/0003-no-composer-use-workflows.md)**
- Implementation plan (created next): `plans/260425-1531-vn-market-data-platform/`
