# VN Market Data Platform

GCP-hosted data lakehouse for Vietnam market data — equities, futures, indices — used for alpha research and quant strategy development.

## What it does

- **Ingests** real-time ticks, L1 + L2 order book, and index updates from SSI FastConnect Data
- **Backfills + refreshes** daily OHLCV, fundamentals, and corporate actions via `vnstock`
- **Stores** everything as Parquet on GCS (`asia-southeast1`), partitioned by date / asset class / symbol
- **Serves** researchers via BigQuery BigLake (SQL), the `vnmarket` Python SDK (Polars/DuckDB), Looker Studio dashboards, and a Streamlit research app
- **Alerts** to Telegram on session events, EOD summaries, and failures (Cloud Monitoring + custom alerter)
- **Runs** trading-calendar-aware on Cloud Scheduler + Cloud Workflows + Cloud Run (no Composer/Airflow)

## Coverage

| Asset class | Universe | Streams |
|---|---|---|
| Equities | All ~1,600 listed (HOSE + HNX + UPCoM) | daily, fundamentals, ticks, L1, L2 |
| Index futures | VN30F1M, VN30F2M, VN30F1Q, VN30F2Q | ticks, L1, L2 |
| Indices | ~30+ (HOSE main/sector/thematic + HNX main/sector + UPCoM main/segments) | intraday + daily |

Historical backfill: **5 years**.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/00-overview.md](docs/00-overview.md) | Spec — exec summary, scope, key decisions, open questions |
| [docs/01-architecture.md](docs/01-architecture.md) | Full design: architecture, data model, components, orchestration, alerting, reliability, testing, cost |
| [docs/adr/](docs/adr/) | Architecture Decision Records for non-obvious choices |

## Status

**Spec phase.** Implementation plan and code to follow.

## Quickstart for local dev

```bash
# 1. Install uv (https://docs.astral.sh/uv/)
# 2. Sync dependencies
uv sync --all-extras

# 3. Authenticate to GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project vn-market-platform-staging

# 4. Run unit tests
uv run pytest -m unit

# 5. (One-time per env) Bootstrap a fresh GCP project
./scripts/bootstrap-gcp-project.sh vn-market-platform-staging "$BILLING_ACCOUNT" staging

# 6. Apply Terraform
cd infra/envs/staging
terraform init
terraform plan
terraform apply
```

See `docs/07-onboarding.md` for full onboarding (Phase 13 deliverable).

## Quick reference

- **Region:** `asia-southeast1` (Singapore)
- **Envs:** `prod`, `staging`, `test`
- **Budget ceiling:** $300/mo GCP (excl. SSI FC subscription)
- **Source of truth for data:** GCS bucket `vn-market-lake-{env}`, raw + curated Parquet
- **Source of truth for schemas:** `sql/schemas/*.sql`
- **Source of truth for trading calendar:** `infra/calendar/vn-trading-days-{year}.json`
