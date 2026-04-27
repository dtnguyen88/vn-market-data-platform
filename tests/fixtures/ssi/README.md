# SSI WebSocket Fixtures (Synthetic)

These fixtures are **synthetic** — hand-crafted to match the documented SSI FastConnect Data WebSocket field abbreviations. They are NOT captured from a live SSI session.

## Field abbreviations

- **ticks:** S=symbol, P=price (1/10 VND), V=volume, T=timestamp_ms, MT=match_type, TID=trade_id, SEQ=seq, EX=exchange, SD=side
- **quotes_l1:** S, T, EX, BP=bid_price, BV=bid_volume, AP=ask_price, AV=ask_volume
- **quotes_l2:** S, T, EX, B (list of up to 10 levels with P=price, V=volume, N=num_orders), A (same structure)
- **indices:** IC=index_code, T=ts_ms, EX, V=value, C=change, CP=change_pct, TVO=total_volume, TVA=total_value, ADV=advance, DEC=decline, UNC=unchanged

## Schema adaptation note

The plan originally referenced `result.bid_px` as a list. This project uses a **flat schema** (`bid_px_1` through `bid_px_10`, etc.) defined in `src/shared/schemas.py` (QuoteL2). Tests use `result.bid_px_1`, `result.bid_px_10`, etc. accordingly.

## Pre-production action item

Before going live, capture ~5 minutes of real SSI WS messages of each type via a one-off script (NOT committed) and replace these fixtures. Verify all parser tests still pass against captured data.
