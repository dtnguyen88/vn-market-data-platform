# ADR-0001 — Pub/Sub from day one (not "v2 if needed")

**Date:** 2026-04-25
**Status:** Accepted
**Context:** [01-architecture.md §1, §3](../01-architecture.md)

## Decision

Adopt Cloud Pub/Sub as the streaming buffer between the realtime publisher and the parquet writers from v1, rather than starting with an in-memory buffer co-located in a single ingester process.

## Context

The first sketch of the architecture (during brainstorm) used an in-memory buffer in a single Cloud Run service: WebSocket consumer + buffer + Parquet writer all in one process, flushed to GCS every 60s. Justified as "simpler and cheaper for v1, add Pub/Sub later if we need fan-out." Expected savings: avoid one extra service + Pub/Sub fees (~$8/mo).

The question was challenged: *why not Pub/Sub now?*

## Considered alternatives

### A. In-memory buffer in single ingester (initial sketch)
- Pros: one less moving part, no Pub/Sub bill (~$8/mo)
- Cons: data loss on crash (up to 60s of ticks); coupled producer/consumer failure modes; no replay; no fan-out without rewrite; backpressure DIY

### B. Pub/Sub from day one (chosen)
- Pros: durability (7-day retention), decoupling, replay, native backpressure, future fan-out is one-line subscription, free observability via Pub/Sub metrics
- Cons: one extra service to deploy, ~$8/mo cost, slightly more code

### C. Cloud Tasks queue
- Pros: simpler than Pub/Sub for low-throughput
- Cons: not designed for high-throughput streaming; ack semantics weaker than Pub/Sub

## Why B wins

1. **Tick data with gaps is poisoned data.** A backtest cannot distinguish "no trade in this 30s window" from "we lost 30s of ticks in a Cloud Run restart." This breaks alpha research correctness silently. In-memory buffer can lose up to 60s on any restart (deploy, autoscale, OOM, region maintenance).
2. **Cost is negligible at our scale.** Pub/Sub at $40/TB ingested × ~5–10 GB/day × 30d = $6–12/mo. Doesn't move the needle against the $300 budget.
3. **Decoupling pays dividends immediately.** Producer (WS reader) and writer (Parquet flusher) have different failure modes. Coupled, a slow GCS write blocks WS reads; decoupled, Pub/Sub absorbs the difference.
4. **Replay is future-proofing for the bug we haven't found yet.** When a parser bug is discovered six months in, replaying from a Pub/Sub snapshot is dramatically cheaper than re-scraping from SSI FC.
5. **Fan-out is free.** Adding ClickHouse as a secondary tick sink (a real possibility per [00-overview.md open questions](../00-overview.md)) becomes one extra subscription rather than a publisher rewrite.
6. **Observability is free.** Pub/Sub native metrics: `oldest_unacked_message_age`, ack-lag, DLQ message count, publish rate per topic. These power the Cloud Monitoring alert policies in [§4.3](../01-architecture.md#43-realtime-gap-detection-3-layers) without writing custom metric code.

## Consequences

- 4 Pub/Sub topics (one per stream type) + 4 DLQs = 8 Pub/Sub resources to provision.
- Publisher and parquet-writer become separate Cloud Run services (8 always-on instances total: 4 publishers × 4 writers).
- ~$8–12/mo Pub/Sub cost added to GCP bill.
- ~1 extra day of dev work for the publisher/subscriber split.
- DLQ drain workflow (see [§7.4](../01-architecture.md#74-dlq-replay)) becomes part of v1 ops surface.

## Reversal

Reversing this would require collapsing publishers + writers into a single service and removing Pub/Sub topics. Not anticipated. The opposite move (adding Pub/Sub later) would have been a much harder migration.
