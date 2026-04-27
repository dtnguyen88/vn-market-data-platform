# 01 — Architecture

> **Spec:** VN Market Data Platform
> **Date:** 2026-04-25
> **Companion:** [00-overview.md](00-overview.md), [adr/](adr/)

Comprehensive technical design. Sections are independent — read what you need.

- [1. Top-level architecture](#1-top-level-architecture)
- [2. Data model & storage layout](#2-data-model--storage-layout)
- [3. Ingestion components](#3-ingestion-components)
- [4. Orchestration & schedule](#4-orchestration--schedule)
- [5. Visualization & researcher access](#5-visualization--researcher-access)
- [6. Alerting & observability](#6-alerting--observability)
- [7. Reliability & error handling](#7-reliability--error-handling)
- [8. Testing strategy](#8-testing-strategy)
- [9. Repo layout](#9-repo-layout)
- [10. Cost model](#10-cost-model)

---

## 1. Top-level architecture

```
SSI FC WS ──▶ realtime-publisher (Cloud Run, min=1, sharded × 4)
                  │
                  ├──▶ Pub/Sub topic: market-ticks       (DLQ: market-ticks-dlq)
                  ├──▶ Pub/Sub topic: market-quotes-l1   (DLQ: ...-l1-dlq)
                  ├──▶ Pub/Sub topic: market-quotes-l2   (DLQ: ...-l2-dlq)
                  └──▶ Pub/Sub topic: market-indices     (DLQ: ...-indices-dlq)
                              │
                              ▼
                  parquet-writer-{ticks,l1,l2,indices}  (Cloud Run, min=1, 60s flush)
                              │
                              ▼
                  GCS  gs://vn-market-lake-{env}/raw/{stream}/date=.../...
                              │
            ┌─────────────────┼──────────────────────────┐
            ▼                 ▼                          ▼
        BigQuery         Notebooks /              (future) ClickHouse
        BigLake ext      Polars / DuckDB           subscriber
        + views          (read GCS direct)
            │
   ┌────────┼─────────┐
   ▼        ▼         ▼
Looker   Streamlit  ad-hoc SQL
Studio   on Cloud Run

Cloud Scheduler ──▶ Cloud Workflows ──▶ Cloud Run Jobs    (orchestration)
Cloud Monitoring + custom metrics ──▶ Pub/Sub ──▶ telegram-alerter (alerting)
```

### 1.1 Tech stack

| Layer | Choice |
|---|---|
| Realtime ingest | Cloud Run service (always-on WebSocket; sharded ×4) |
| Streaming buffer | Pub/Sub (4 topics + DLQs) |
| Batch ingest | Cloud Run Jobs |
| Object storage | GCS, single bucket per env |
| Format | Parquet (zstd-3) + Hive partitioning |
| Query layer | BigQuery BigLake external tables + materialized views |
| Orchestration | Cloud Scheduler + Cloud Workflows |
| Calendar | `infra/calendar/vn-trading-days-{year}.json` (deployed to GCS) |
| Secrets | Secret Manager |
| Visualization (market) | Looker Studio |
| Visualization (research) | Streamlit on Cloud Run |
| Visualization (ops) | Cloud Monitoring dashboards + Workflows console |
| Alerting | Custom `telegram-alerter` Cloud Run, fed by Cloud Monitoring + Pub/Sub |
| IaC | Terraform |
| CI/CD | GitHub Actions → Cloud Build → Cloud Run/Workflows deploy |
| Languages | Python 3.12 (services), SQL (BQ), HCL (Terraform) |

---

## 2. Data model & storage layout

### 2.1 GCS bucket structure (medallion / bronze-silver)

```
gs://vn-market-lake-{env}/
├── raw/                              # Bronze: append-only, exactly what source emitted
│   ├── ticks/date=YYYY-MM-DD/asset_class=.../symbol=.../part-{shard}-{ts}.parquet
│   ├── quotes-l1/date=YYYY-MM-DD/asset_class=.../symbol=.../part-{shard}-{ts}.parquet
│   ├── quotes-l2/date=YYYY-MM-DD/asset_class=.../hour=HH/symbol=.../part-{shard}-{ts}.parquet
│   ├── indices/date=YYYY-MM-DD/index=.../part-{shard}-{ts}.parquet
│   ├── daily-ohlcv/year=YYYY/part-N.parquet
│   ├── fundamentals/quarter=YYYYQN/part-N.parquet
│   ├── corp-actions/year=YYYY/part-N.parquet
│   └── reference/{tickers,futures_contracts}/snapshot=YYYY-MM-DD/*.parquet
├── curated/                          # Silver: deduped, typed, schema-enforced
│   └── (mirrors raw/ structure)
└── _ops/
    ├── ingest-receipts/              # one row per file written, audit + gap detection
    ├── dlq-export/                   # DLQ messages exported nightly
    ├── parse-errors/                 # raw payloads that failed parse
    ├── rejected/                     # rows that failed schema validation
    ├── permanent-gaps/               # holes that cannot be backfilled
    ├── data-quality-issues/          # weekly validator findings
    ├── calendar/                     # runtime copy of holiday JSONs
    └── checksums/
```

- **L2 quotes get `hour=` partition** (highest volume).
- **Indices partitioned by `index=` instead of `symbol=`** (semantic clarity).
- **No `_SUCCESS` markers**; ingest-receipts written to `_ops/` after each successful flush.

### 2.2 Canonical schemas

**ticks** (equities + futures + indices ticks share one schema):
```
ts_event           timestamp[ns, Asia/Ho_Chi_Minh]   # exchange ts
ts_received        timestamp[ns, UTC]                # ingester clock
symbol             string
asset_class        string                            # enum: equity|future|index
exchange           string                            # HOSE|HNX|UPCoM|HNX-DERIV
price              int64                             # 1/10 VND
volume             int64
match_type         string                            # ATO|continuous|ATC|put-through
side               string                            # B|S|? (aggressor)
trade_id           string                            # exchange trade id, dedup key
seq                int64                             # SSI sequence number
```

**quotes_l1:**
```
ts_event, ts_received, symbol, asset_class, exchange
bid_price          int64
bid_size           int64
ask_price          int64
ask_size           int64
mid_price          int64                             # computed at ingest
spread_bps         int32                             # computed at ingest
```

**quotes_l2** (flat, 40+ cols — faster than nested for BQ):
```
ts_event, ts_received, symbol, asset_class, exchange
bid_px_1..bid_px_10        int64
bid_sz_1..bid_sz_10        int64
bid_n_1..bid_n_10          int32     # # orders at level
ask_px_1..ask_px_10        int64
ask_sz_1..ask_sz_10        int64
ask_n_1..ask_n_10          int32
```

**index_values** (intraday, ~3s cadence during sessions):
```
ts_event, ts_received
index_code         string             # VNINDEX|VN30|VN100|HNXINDEX|HNX30|UPCOM|...
exchange           string
value              double             # index level
change             double
change_pct         double
total_volume       int64              # session-cumulative constituent volume
total_value        int64              # session-cumulative constituent traded value (VND)
advance_count      int32
decline_count      int32
unchanged_count    int32
```

**daily_ohlcv:**
```
date, symbol, asset_class, exchange
open, high, low, close      int64
volume, value               int64
adj_close                   int64     # split/dividend adjusted (computed in curated)
foreign_buy_vol             int64
foreign_sell_vol            int64
```

**fundamentals** (quarterly):
```
as_of_date, symbol, period
pe, pb, eps, bvps, roe, roa, debt_to_equity   double
market_cap                                      int64
revenue, net_income, total_assets, total_equity int64
```
> **Implementation note:** the columns above are the v1 minimum. The full vnstock response shape for `fundamentals` may include additional ratios/line-items (e.g. CFO, EBITDA, gross_margin). During implementation, the actual response will be inspected once and the schema extended; new columns added to the curated layer will be backwards-compatible additions only (see [§7.6 Schema evolution](#76-schema-evolution)).

**corp_actions:**
```
ex_date, symbol, action_type   # dividend_cash|dividend_stock|split|rights|merger
ratio, amount   record_date, payment_date
```

**reference/tickers** (daily snapshot):
```
symbol, name, exchange, asset_class, sector_l1, sector_l2, industry,
listed_date, status, lot_size, tick_size, foreign_room_pct
```

**reference/futures_contracts:**
```
symbol, underlying_index, expiry_date, contract_size, tick_size, margin_pct
```

**Calendar JSON** (`infra/calendar/vn-trading-days-{year}.json`):
```json
{ "year": 2026,
  "trading_days": ["2026-01-02", ...],
  "holidays": [{"date": "2026-04-30", "name": "Reunification Day"}, ...],
  "sessions": {
    "equity":     [["09:00","11:30"], ["13:00","14:45"]],
    "derivative": [["08:45","11:30"], ["13:00","14:45"]]
  }
}
```

### 2.3 Schema conventions

- **Prices stored as `int64` in 1/10 VND** — avoids float precision issues.
- **`asset_class` enum**: `equity|future|index`. Filter, don't join.
- **`schema_version`** as a Parquet metadata key on every file.
- **Curated layer** is a full-overwrite-by-partition idempotent rebuild from raw.

### 2.4 BigQuery BigLake surface

| Table | Source | Purpose |
|---|---|---|
| `vnmarket.ticks_raw` | `raw/ticks/**` | audit/debug |
| `vnmarket.ticks` | `curated/ticks/**` | researcher default |
| `vnmarket.quotes_l1` | `curated/quotes-l1/**` | |
| `vnmarket.quotes_l2` | `curated/quotes-l2/**` | |
| `vnmarket.index_values` | `curated/indices/**` | |
| `vnmarket.daily_ohlcv` | `curated/daily-ohlcv/**` | |
| `vnmarket.fundamentals` | `curated/fundamentals/**` | |
| `vnmarket.corp_actions` | `curated/corp-actions/**` | |
| `vnmarket.tickers` | `curated/reference/tickers/**` | |
| `vnmarket.futures_contracts` | `curated/reference/futures_contracts/**` | |

**Materialized views** (refresh nightly):
- `v_top_of_book` — last L1 per symbol per day (for Looker)
- `v_session_vwap` — VWAP per symbol per day per session
- `v_daily_factors` — daily returns, gap, range, ATR (research starter pack)

---

## 3. Ingestion components

| Service | Type | Trigger | Concurrency | Min instances |
|---|---|---|---|---|
| `realtime-publisher-shard-{0..3}` | Cloud Run service | always-on | 1 (singleton per shard) | 1 each = 4 |
| `parquet-writer-ticks/l1/l2/indices` | Cloud Run service | Pub/Sub push | 1–5 per writer | 1 each = 4 |
| `batch-ingester-eod` | Cloud Run Job | Scheduler 16:00 ICT | up to 50 parallel tasks | 0 |
| `batch-ingester-reference` | Cloud Run Job | Scheduler 06:00 ICT | 1 | 0 |
| `curate-{stream}` | Cloud Run Job | Workflows after EOD | 4 (one per stream) | 0 |
| `backfill` | Cloud Run Job | manual | 1–10 parallel tasks | 0 |

**8 always-on Cloud Run instances.** ~$30–40/mo.

### 3.1 Realtime publisher (sharded)

- **Sharding:** `shard_id = murmurhash(symbol) % 4`. Static, in YAML config. Indices all to shard-0.
- **Why min=max=1 per shard:** WebSocket is stateful; autoscaling would multiply connections.
- **Crash:** Cloud Run restarts <5s; Pub/Sub at-least-once on resume; gaps caught by intraday coverage check.
- **Heartbeat** custom metric every 30s.

### 3.2 Parquet writers

- **Buffer:** in-memory ring per `(asset_class, symbol)`, flushed when **60s** OR **50 MB uncompressed** — whichever first.
- **Compression:** zstd level 3.
- **Receipt:** after GCS PUT, append row to `_ops/ingest-receipts/{date}/receipts.jsonl`.
- **Retry:** Pub/Sub 5x exp backoff → DLQ.
- **Schema-rejected rows** → `_ops/rejected/`.

### 3.3 Batch EOD ingester (vnstock)

```
batch-ingester-eod
  triggered: 16:00 ICT trading days
  steps:
    1. Daily OHLCV — all ~1600 equities, asyncio fan-out 50-wide
    2. Daily indices (~30) + daily futures (4)
    3. Fundamentals (only on quarterly report dates)
    4. Corp actions (next 30 days)
    5. Write raw/
    6. Trigger curated build for today
    7. Telegram EOD summary
  timeout: 30 min, idempotent (overwrite today's file)
```

Fallback chain: TCBS → VCI → SSI HTML for vnstock sources.

### 3.4 Reference data ingester

```
batch-ingester-reference
  triggered: 06:00 ICT daily
  pulls: ticker master, futures specs, sector mapping, foreign room limits
  writes: raw/reference/.../snapshot=YYYY-MM-DD/*.parquet
```

### 3.5 Curated layer builder

```
curate-{stream}   (one per stream type)
  triggered: Workflows nightly 17:00 ICT (or backfill mode)
  reads: raw/{stream}/date=YYYY-MM-DD/**
  ops:
    - dedupe by (symbol, ts_event, trade_id) for ticks; (symbol, ts_event) for quotes/indices
    - timezone normalize, type coerce
    - reject schema fails -> _ops/rejected/
    - re-partition to ~128 MB target files
    - compute derived: mid_price, spread_bps; adj_close from corp_actions
  writes: curated/{stream}/date=YYYY-MM-DD/**
  full overwrite of partition; idempotent
```

### 3.6 Backfill runner

```
backfill   (one-shot Cloud Run Job)
  args: --start --end --streams=...
  parallel tasks (Cloud Run Jobs supports parallelism)
  skips dates already present (checked via _ops/ingest-receipts)
```

---

## 4. Orchestration & schedule

### 4.1 Workflow inventory

| # | Workflow | Cron (ICT) | Purpose |
|---|---|---|---|
| 1 | `eod-pipeline` | `0 16 * * 1-5` | Daily ingest + curate + view refresh + EOD report |
| 2 | `reference-refresh` | `0 6 * * 1-5` | Pull tickers/contracts/sectors snapshot |
| 3 | `intraday-coverage-check` | `*/5 9-15 * * 1-5` | Per-symbol coverage poll (5-min) |
| 4 | `curate-fallback` | `0 17 * * 1-5` | Rerun curate-only if `eod-pipeline` failed (idempotent) |
| 5 | `calendar-refresh-yearly` | `0 0 1 12 *` | Scrape HOSE next-year holidays, send diff alert |
| 6 | `monthly-cost-report` | `0 9 1 * *` | Pull billing, Telegram cost summary |

Every workflow's first step: `check_trading_day()` against calendar JSON.

### 4.2 EOD pipeline DAG

```
check_trading_day → batch-ingester-eod →
  ┌─ curate-ticks ─┐
  ├─ curate-l1   ──┤
  ├─ curate-l2   ──┼─→ refresh BQ MVs → gap-detection-eod → telegram-eod-report
  ├─ curate-indices┤
  └─ curate-daily ─┘

ON ANY FAILURE: telegram-failure-alert(step, error, log_link); workflow continues for independent steps.
```

**Step retry:** 3 attempts, exp backoff (10s → 60s → 5min).

### 4.3 Realtime gap detection (3 layers)

| Layer | Mechanism | Latency | Catches |
|---|---|---|---|
| 1: Cloud Monitoring alert policy on **publisher heartbeat absence** >90s | event-driven | 60–90s | publisher dead |
| 1: Cloud Monitoring alert on **Pub/Sub publish rate = 0** during session >120s | event-driven | ~120s | feed silent / SSI auth expired |
| 1: Cloud Monitoring alert on **subscription oldest-unacked age** >180s | event-driven | ~60s | writer backpressure |
| 2: `intraday-coverage-check` workflow (5-min) | poll | ≤5 min | per-symbol coverage drops |
| 3: EOD audit step in `eod-pipeline` | EOD | end of day | full daily reconciliation |

### 4.4 Trading calendar

- Source of truth: `infra/calendar/vn-trading-days-{year}.json` in repo (PR-controlled).
- Deployed to `gs://vn-market-lake-{env}/_ops/calendar/{year}.json` at CI time.
- Yearly `calendar-refresh-yearly` workflow scrapes HOSE next-year holidays, posts Telegram diff if mismatch — operator commits update.

### 4.5 Publisher lifecycle

**Always-on for v1.** Scale-to-zero outside trading hours deferred (saves ~$20/mo, costs cold-start risk + 2 workflows).

---

## 5. Visualization & researcher access

### 5.1 Market dashboards — Looker Studio

| Dashboard | Source | Default content |
|---|---|---|
| Market Overview | `v_top_of_book` + `v_session_vwap` + `index_values` | VNINDEX/VN30/HNX30 candle, gainers/losers, sector heatmap, foreign net buy, breadth |
| Symbol Detail | `quotes_l1`, `quotes_l2`, `ticks` | filterable — intraday price+vol, last 10-level book, trade tape, fundamentals row |
| Futures Board | `v_top_of_book` filtered to futures | VN30F1M-F2Q price/basis vs VN30, OI proxy, term structure |

Dashboard JSONs exported to `infra/looker/`.

### 5.2 Pipeline health

- **Cloud Monitoring dashboard `vn-platform-ops`** (Terraform-managed)
- **Cloud Workflows console** for DAG visualization
- **Cloud Logging saved queries** (Terraform-managed)
- **Telegram chat history** = audit trail

### 5.3 Streamlit research app

`research-app` Cloud Run service, IAM-protected:

| Page | Purpose |
|---|---|
| Universe Explorer | ticker(s) + date range → chart, stats, fundamentals |
| Microstructure Inspector | ticker + minute → L2 evolution + tick tape + spread/imbalance |
| Backtest Snapshot Viewer | upload backtest Parquet → equity curve, drawdown, exposure, attribution |

Cost ~$5/mo (min=0, ~3s cold start acceptable).

### 5.4 vnmarket Python SDK (the daily driver)

```python
import vnmarket as vm
client = vm.Client(project="vn-market-platform-prod", env="prod")

df    = client.daily(symbols=["VNM","VHM","VIC"], start="2024-01-01", end="2026-04-25")
ticks = client.ticks(symbol="VNM", date="2026-04-25").collect()
book  = client.l2_at(symbol="VHM", ts="2026-04-25 10:30:15.000")
idx   = client.index(code="VN30", start="2026-01-01")
df    = client.sql("SELECT symbol, AVG(spread_bps) FROM vnmarket.quotes_l1 WHERE date='2026-04-25' GROUP BY symbol")
```

- **Read path:** Parquet from GCS via pyarrow.dataset + Polars (no BQ slot consumption); BQ Storage Read API as fallback.
- **Caching:** `~/.vnmarket/cache/` LRU, 10 GB default.
- **Gap awareness:** consults `_ops/permanent-gaps/`; returns explicit `null` rows.
- **Notebook starter pack:** `notebooks/00-quickstart.ipynb`, `01-cross-sectional-momentum.ipynb`, `02-microstructure-spread-decay.ipynb`.
- **Auth:** `gcloud auth application-default login` once.

---

## 6. Alerting & observability

### 6.1 Telegram alerter

```
telegram-alerter   (Cloud Run, min=0, max=3)
  endpoint: POST /alert  (Pub/Sub push subscription)
  responsibilities:
    - validate payload schema
    - dedupe within 10-min window (key: alert_name + severity + scope)
    - format with severity emoji + Cloud Logging deep-link
    - rate-limit: 30 msg/min (Telegram Bot API limit)
    - send to your Telegram chat via Bot API
    - on send failure: retry 3x, then ack (alert lost — accept)
  state: Firestore for dedup
```

### 6.2 Severity taxonomy

| Severity | Emoji | Examples | Suppression |
|---|---|---|---|
| critical | 🔴 | publisher dead, topic silent, EOD failed | none |
| warning | 🟠 | per-symbol coverage drop, ack-lag elevated, schema reject spike | 10 min |
| info | ✅ | session start/end, EOD success, monthly cost | 60 min |
| debug | 🔵 | (off by default; toggle via env var) | 5 min |

### 6.3 Default messages

- **Session start (08:35):** `✅ vn-market-platform / {date} — Trading session opening. Window 08:40–15:05 ICT. Publishers: 4 shards healthy.`
- **EOD success (~17:30):** row counts per stream, gaps detected, curated build duration, GCS bytes written, today's est cost.
- **EOD failure:** step name, error message, deep-link to logs and workflow run.
- **Critical realtime:** affected service, signal that triggered, last-healthy timestamp, deep-link to logs.

### 6.4 Custom metrics

| Metric | Type | Emitted by |
|---|---|---|
| `publisher_heartbeat` | gauge, 30s | publisher shards |
| `publisher_messages_received` | counter | publisher shards |
| `writer_buffer_size_bytes` | gauge, 10s | parquet-writers |
| `writer_flush_duration_ms` | histogram | parquet-writers |
| `gcs_write_errors_total` | counter | parquet-writers |
| `dlq_message_count` | gauge (built-in) | Pub/Sub |
| `curated_rows_processed` | counter | curate jobs |
| `cost_today_usd` | gauge | cost-report job |

### 6.5 Cost observability

- **Daily mode** (23:00 ICT): query Billing BQ export, emit `cost_today_usd`, used in EOD report.
- **Monthly mode** (1st 09:00 ICT): prior-month total + breakdown + top 5 line items + MTD trend alert if >$300.
- **Cloud Billing budget alert**: $250 (warning), $290 (critical) → Telegram.

### 6.6 SLO intent (no formal SLOs in v1)

| Capability | Target |
|---|---|
| Tick capture during session | 99% expected messages within 5 min |
| Daily OHLCV freshness | available by 17:00 ICT trading day |
| Curated layer freshness | available by 18:00 ICT trading day |
| Critical alert latency | <2 min |
| Telegram message budget | <30/day average |

---

## 7. Reliability & error handling

### 7.1 Failure mode matrix (key scenarios)

| Component | Failure | Detection | Recovery | Data loss? |
|---|---|---|---|---|
| Publisher | SSI WS disconnect | heartbeat alert | auto-reconnect exp backoff (5s→2m), resubscribe | gap during reconnect (flagged) |
| Publisher | SSI auth expired | publish rate=0 alert | refresh from Secret Manager, reauth | up to outage window |
| Publisher | Container OOM | heartbeat alert | Cloud Run restart <5s; Pub/Sub state preserved | none |
| Publisher | Schema parse error | log + metric | drop msg, write raw payload to `_ops/parse-errors/` | this msg only |
| Writer | GCS write fails | retry, then DLQ | auto-retry 5x exp backoff | none — DLQ replay |
| Writer | OOM | restart | Pub/Sub redelivers unacked | none |
| Writer | Schema reject | log | row → `_ops/rejected/`, ack msg | this row only |
| Batch ingester | vnstock source down | step retry | fallback chain TCBS → VCI → SSI HTML | none if any source works |
| Batch ingester | all sources down | workflow fail alert | retry next day; backfill re-runs | daily gap until next run |
| Curate | bad input partition | step fail alert | re-run on raw/ (idempotent) | none |
| BQ MV refresh | quota / slot exhaustion | step fail | retry next EOD | stale view 1 day |
| Calendar JSON | missing year on Jan 1 | startup check | bootstrap with prev year + Telegram alert | none |

### 7.2 Idempotency

- **Raw layer:** files have deterministic name `part-{shard}-{ts}.parquet`; re-runs append; dedup at curate.
- **Curated layer:** full-overwrite of `date=YYYY-MM-DD` partition.
- **Daily/fundamentals/reference:** overwrite by date / snapshot.

→ Any failed run can be re-run without manual cleanup.

### 7.3 Retry policies

| Layer | Policy |
|---|---|
| Pub/Sub subscription | 5 attempts, exp 10s base, max 600s |
| Cloud Run Jobs | 3 attempts, exp |
| Workflows steps | 3 attempts, 10s/60s/300s; non-retriable for schema errors |
| HTTP client (vnstock) | 4 attempts, jitter |
| GCS client | 3 retries (built-in), idempotency tokens |

### 7.4 DLQ replay

DLQ topics drained nightly by `dlq-drain` Cloud Run Job:
- exports messages to `gs://.../_ops/dlq-export/{date}/{topic}.jsonl.zst`
- Telegram if count > 0
- **manual** replay via `gcloud run jobs execute dlq-replay --args="--export=...jsonl.zst --topic=..."`

### 7.5 Backfill flow

For realtime streams: SSI FC historical typically goes back ~1y for ticks; gaps that can't be filled recorded in `_ops/permanent-gaps/`. SDK exposes gaps as first-class concept.

For batch streams: re-run vnstock pulls per date, idempotent overwrite.

### 7.6 Schema evolution

- `schema_version` Parquet metadata key on every file.
- Curated layer dispatches per version.
- Migrations = re-run curate over historical raw partitions.
- **Forbidden:** removing/renaming columns without version bump.

### 7.7 Disaster recovery

| Scenario | RPO | RTO | Mitigation |
|---|---|---|---|
| Cloud Run instance crash | 0 | <30s auto-restart | built-in |
| Single shard publisher silent | 0–90s | <2 min | heartbeat alert; sharding limits blast to ~25% |
| Pub/Sub regional outage | 0 if <7 days | outage duration | GCP responsibility |
| GCS bucket corruption | depends | hours | versioning ON, lifecycle 30d |
| BQ views broken | 0 (raw+curated intact) | minutes | view defs in IaC |
| Repo loss | 0 | hours | git + GitHub |
| SSI account suspended | high | days | contractual; vnstock keeps daily flowing |

### 7.8 Backup strategy

- **GCS bucket versioning ON**, 30d lifecycle on non-current versions (~+10% storage).
- **No cross-region replication** in v1.
- **No point-in-time DB backup** — raw GCS is the backup.

---

## 8. Testing strategy

```
                   E2E smoke (3)         manual + nightly
                Integration (~30)        per PR, GCP test project
                  Unit (~150)            per commit, no GCP
```

### 8.1 Unit tests

| Target | Surface |
|---|---|
| SSI parsers | golden-fixture replay → expected dataclass |
| Schema validators | reject bad / accept good |
| Buffer + flush logic | thresholds, race conditions |
| Calendar logic | holidays, half-days, sessions |
| Sharding hash | symbol→shard stable across releases |
| `vnmarket` SDK transforms | Polars frames typed/sorted correctly |
| Curate dedup | identical events collapse |
| Adj-close computation | known split/dividend cases |
| Telegram message templates | snapshot tests |

### 8.2 Integration tests (against dedicated `test` GCP project)

- Pub/Sub publish→subscribe roundtrip
- GCS Parquet write + read-back
- BigLake external table query
- Cloud Run Job execution (stubbed vnstock)
- Workflows execution (full eod-pipeline with stubs)
- Telegram alerter (mock Bot endpoint)

### 8.3 Contract tests (nightly, real external sources)

- SSI FC WS schemas for sampled symbols
- vnstock daily / fundamentals endpoints
- HOSE holiday calendar page parseability

Failure → Telegram warning, doesn't block PRs.

### 8.4 E2E smoke

1. `smoke_realtime_45min` — replay 45 min of recorded SSI WS in staging, assert GCS rows + BigLake counts + zero DLQ.
2. `smoke_eod_pipeline` — full workflow against staging for known historical date.
3. `smoke_research_sdk` — fresh notebook runs `00-quickstart.ipynb`.

### 8.5 Data correctness validators (weekly, real prod data)

| Job | Asserts |
|---|---|
| `validate-tick-vs-daily` | `SUM(ticks.value)` per symbol per day = `daily.total_value` ±0.5% |
| `validate-l1-vs-l2` | `quotes_l1.bid_price == quotes_l2.bid_px_1` at same `ts_event` |
| `validate-index-recompute` | recomputed VN30 from constituents = `index_values.value` ±0.1% |
| `validate-corp-actions-applied` | `daily.adj_close` consistency across split events |

Failures → Telegram + flag in `_ops/data-quality-issues/`.

### 8.6 CI/CD

```
.github/workflows/
  ├── unit.yml          per push: lint + unit, ~3 min
  ├── integration.yml   per PR + main: ~15 min, against test GCP project
  ├── contract.yml      nightly cron: alert-on-fail
  ├── deploy-staging.yml on merge to main: terraform plan+apply, deploy services
  └── deploy-prod.yml   manual approval + tag: terraform plan+apply, deploy services
```

- PR feedback target <20 min total.
- Coverage target 70% line on `src/`, **not gated**.
- Linters: `ruff`, `tflint`, `sqlfluff`.

---

## 9. Repo layout

```
Data_Platform_2/
├── README.md
├── pyproject.toml             # uv-managed single workspace
├── uv.lock
├── .python-version            # 3.12
├── .pre-commit-config.yaml
├── .gitignore
├── .github/workflows/{unit,integration,contract,deploy-staging,deploy-prod}.yml
│
├── docs/
│   ├── 00-overview.md
│   ├── 01-architecture.md         (this file)
│   ├── 02-data-model.md           (split-out detail of §2 — created later)
│   ├── 03-orchestration.md        (split-out detail of §4 — created later)
│   ├── 04-alerting.md             (split-out detail of §6 — created later)
│   ├── 05-runbook-incident.md     (created during impl)
│   ├── 06-runbook-backfill.md     (created during impl)
│   ├── 07-onboarding.md           (created during impl)
│   └── adr/
│       ├── 0001-pubsub-from-day-one.md
│       ├── 0002-gcs-parquet-lakehouse.md
│       └── 0003-no-composer-use-workflows.md
│
├── infra/                     # Terraform IaC
│   ├── envs/{staging,prod}/
│   ├── modules/{gcs-bucket, pubsub-topic, cloud-run-service, cloud-run-job, workflow, scheduler, monitoring-alert, biglake-table}/
│   ├── workflows/{eod-pipeline, intraday-coverage-check, reference-refresh, curate-fallback, calendar-refresh-yearly, monthly-cost-report}.yaml
│   ├── monitoring/{dashboards.tf, alert-policies.tf}
│   ├── looker/                # exported dashboard JSONs (3)
│   ├── calendar/vn-trading-days-{2021..2026}.json
│   └── secrets/               # secret names only
│
├── src/
│   ├── vnmarket/              # researcher SDK
│   │   ├── __init__.py, client.py, schemas.py, gaps.py
│   │   └── readers/{parquet.py, bq.py, cache.py}
│   │
│   ├── publisher/
│   │   ├── __main__.py, ws_client.py, shard.py, pubsub_publisher.py, heartbeat.py, config.py, Dockerfile
│   │   └── parsers/{ticks.py, quotes_l1.py, quotes_l2.py, indices.py}
│   │
│   ├── writers/
│   │   ├── __main__.py        # CLI: --stream={ticks|l1|l2|indices}
│   │   ├── buffer.py, parquet_writer.py, gcs_uploader.py, receipts.py, schema_validator.py, Dockerfile
│   │
│   ├── batch/
│   │   ├── eod/{__main__.py, vnstock_pulls.py, fundamentals.py, corp_actions.py, Dockerfile}
│   │   ├── reference/{__main__.py, tickers.py, futures.py, Dockerfile}
│   │   └── backfill/{__main__.py, Dockerfile}
│   │
│   ├── curate/
│   │   ├── __main__.py, dedup.py, partitioner.py, derived_columns.py, adjustments.py, Dockerfile
│   │
│   ├── alerter/
│   │   ├── __main__.py, dedupe.py, formatter.py, telegram_client.py, rate_limiter.py, Dockerfile
│   │
│   ├── research_app/
│   │   ├── __main__.py, Dockerfile
│   │   └── pages/{1_universe_explorer.py, 2_microstructure.py, 3_backtest_viewer.py}
│   │
│   ├── ops/{cost_report, dlq_drain, coverage_check, data_quality}/
│   │
│   └── shared/
│       └── {calendar.py, secrets.py, gcp.py, logging_setup.py, metrics.py}
│
├── notebooks/{00-quickstart, 01-cross-sectional-momentum, 02-microstructure-spread-decay}.ipynb
│
├── sql/
│   ├── schemas/{ticks, quotes_l1, quotes_l2, index_values, daily_ohlcv, fundamentals, corp_actions, tickers, futures_contracts}.sql
│   └── views/{v_top_of_book, v_session_vwap, v_daily_factors}.sql
│
├── tests/{unit, integration, contract, e2e}/ + fixtures/{ssi, vnstock}/
│
└── scripts/{bootstrap-gcp-project, deploy-services, run-backfill, invoke-dlq-replay}.sh
```

### 9.1 Conventions

- **Single uv workspace**, one shared lockfile across services.
- **One Dockerfile per Cloud Run unit**, 4 writer types collapsed into one image with `--stream` arg → **7 images total**.
- **All Python files under 200 LoC** per CLAUDE.md modularization rule.
- **No cross-service imports** except `shared/`.
- **`vnmarket` SDK has zero coupling** to ingester code (clean read-side, pip-installable standalone).

---

## 10. Cost model

### 10.1 Steady-state (year 5, full universe, 5y accumulated)

| Service | Driver | Est cost |
|---|---|---|
| GCS storage (~5.5 TB raw + curated + 10% versioning) | storage | $110 |
| GCS class A/B operations | reads + writes | $5 |
| Pub/Sub | ingest ~5–10 GB/day across 4 topics | $20–40 |
| Cloud Run services (always-on) | 8 services × 256 MiB × 0.5 vCPU × 730h | $30 |
| Cloud Run Jobs (compute) | batch + curate ~30 min/day | $5 |
| Cloud Run egress | small | $5 |
| BigQuery | BigLake ~100 GB scanned/mo (moderate research) | $5–30 |
| BQ MV storage | tiny | $1 |
| Cloud Logging | ~30 GB/mo (50 GB free) | $0 |
| Cloud Monitoring | ~20 custom metrics (150 free) | $0–5 |
| Cloud Scheduler | 6 jobs × pennies | $0 |
| Cloud Workflows | ~3,000 steps/mo | $0 |
| Secret Manager | ~10 secrets | $1 |
| Cloud Build (CI/CD) | minutes used | $5 |
| Artifact Registry | ~10 GB images | $1 |
| Network egress | ~50 GB/mo research downloads | $5 |
| Looker Studio | — | $0 |
| **GCP total** | | **~$190–235/mo** |
| **+ SSI FC subscription** | external | ~$50–200/mo |
| **Combined** | | **~$240–435/mo** |

### 10.2 Ramp profile

| Phase | When | GCP cost |
|---|---|---|
| 0: bootstrap | Month 0–1: infra + 5y backfill of daily/fundamentals/reference | ~$30/mo |
| 1: realtime live | Month 2–3 | ~$60–90/mo |
| 2: 1y realtime accumulated | Month 12 | ~$110/mo |
| 3: 3y accumulated | Year 3 | ~$160/mo |
| 4: 5y steady state | Year 5+ | ~$200–235/mo |

### 10.3 Cost levers (documented, not pre-applied)

In priority order:
1. Move L2 raw partitions >90d to **Coldline** lifecycle: -$30–50/mo (slower first read of cold)
2. Drop versioning on raw/ (keep on curated/): -$8/mo
3. Scale publishers/writers to 0 outside trading hours: -$15–20/mo (cold-start risk)
4. Reduce L2 retention to 2y: -$40–60/mo
5. Drop UPCoM L2: -$20–30/mo
6. Switch daily/fundamentals to BQ native tables: nominal

### 10.4 Quotas

All within default GCP quotas. Cloud Run Jobs concurrent executions (default 10/region) — request bump to 50 pre-backfill.

### 10.5 Hard cost guardrails

- Cloud Billing budget alerts at $250 / $290 → Telegram
- Daily cost in EOD report
- Monthly cost report on 1st with prior month + MTD trend

### 10.6 Region & environments

- **Single region:** `asia-southeast1` (Singapore) — closest to SSI FC, cheapest.
- **Three envs:** `prod` ($200–235), `staging` (<$30 mostly idle), `test` (<$10, ephemeral resources lifecycle-deleted nightly).

---

**End of architecture spec.**
