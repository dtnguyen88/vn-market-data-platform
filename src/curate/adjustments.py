"""Backward-adjustment of daily close prices from corporate actions.

Computes adj_close = close * Π factor(action) over ex_dates > current date.

References: standard CRSP-style backward adjustment.
"""

import polars as pl
import structlog

log = structlog.get_logger(__name__)


def _action_factor(
    action_type: str,
    ratio: float | None,
    amount: float | None,
    close_prev: float | None,
) -> float:
    """Factor to multiply prior-date close to get backward-adjusted price."""
    if action_type == "split":
        return 1.0 / ratio if ratio and ratio > 0 else 1.0
    if action_type in ("dividend_stock", "rights"):
        return 1.0 / (1.0 + ratio) if ratio is not None and ratio > 0 else 1.0
    if action_type == "dividend_cash":
        if not amount or not close_prev or close_prev <= 0:
            log.warning(
                "dividend_cash: missing close_prev or amount, skipping",
                amount=amount,
                close_prev=close_prev,
            )
            return 1.0
        return (close_prev - amount) / close_prev
    # merger or unknown: no-op for v1
    return 1.0


def _cumulative_factor(d, ex_dates: list, factors: list) -> float:
    """Product of factors where ex_date > d."""
    prod = 1.0
    for ex, f in zip(ex_dates, factors, strict=False):
        if ex > d:
            prod *= f
    return prod


def apply_adjustments(
    daily_df: pl.DataFrame,
    corp_actions_df: pl.DataFrame,
) -> pl.DataFrame:
    """Add adj_close column to daily_df via backward-adjustment from corp actions.

    For each (symbol, date), adj_close = close * Π factor(action_i) over all
    corporate actions with ex_date_i > date for the same symbol.

    If corp_actions_df is empty, adj_close = close for all rows.
    """
    if corp_actions_df.height == 0:
        return daily_df.with_columns(pl.col("close").cast(pl.Int64).alias("adj_close"))

    # Sort actions by (symbol, ex_date)
    actions = corp_actions_df.sort(["symbol", "ex_date"]).clone()

    # Build (symbol, ref_date, ref_close) lookup for close_prev calculation.
    # join_asof backward strategy finds most recent ref_date < ex_date per symbol.
    daily_sorted = daily_df.sort(["symbol", "date"])
    closes = daily_sorted.select(["symbol", "date", "close"]).rename(
        {"date": "ref_date", "close": "ref_close"}
    )

    # Attach close_prev = close on trading day strictly before ex_date.
    # join_asof "backward" strategy is inclusive (<=), so subtract 1 day from
    # ex_date before joining to ensure we find the most recent date < ex_date.
    actions_shifted = actions.with_columns(ex_date_minus1=pl.col("ex_date") - pl.duration(days=1))
    actions_with_prev = actions_shifted.join_asof(
        closes,
        left_on="ex_date_minus1",
        right_on="ref_date",
        by="symbol",
        strategy="backward",
    ).with_columns(close_prev=pl.col("ref_close").cast(pl.Float64))

    # Compute factor per corporate action row
    factors = actions_with_prev.with_columns(
        factor=pl.struct(["action_type", "ratio", "amount", "close_prev"]).map_elements(
            lambda s: _action_factor(s["action_type"], s["ratio"], s["amount"], s["close_prev"]),
            return_dtype=pl.Float64,
        )
    ).select(["symbol", "ex_date", "factor"])

    # For each daily row, multiply all factors whose ex_date > row date.
    # Process per symbol; corp actions are sparse so this is manageable.
    out_rows: list[pl.DataFrame] = []
    for sym in daily_df["symbol"].unique().to_list():
        sym_daily = daily_df.filter(pl.col("symbol") == sym)
        sym_factors = factors.filter(pl.col("symbol") == sym)

        if sym_factors.height == 0:
            sym_daily = sym_daily.with_columns(pl.col("close").cast(pl.Float64).alias("adj_close"))
        else:
            ex_dates = sym_factors["ex_date"].to_list()
            facs = sym_factors["factor"].to_list()
            sym_daily = sym_daily.with_columns(
                adj_close=pl.col("date").map_elements(
                    lambda d, eds=ex_dates, fs=facs: _cumulative_factor(d, eds, fs),
                    return_dtype=pl.Float64,
                )
                * pl.col("close").cast(pl.Float64),
            )

        out_rows.append(sym_daily)

    return pl.concat(out_rows).with_columns(pl.col("adj_close").cast(pl.Int64))
