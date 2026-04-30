"""Universe Explorer — symbol-level daily OHLCV with charts + stats.

Modes:
- Single symbol: candlestick + volume + KPI strip + recent rows.
- Compare 2-6 symbols: normalized return overlay + per-symbol KPIs.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import vnmarket as vm
from research_app.auth import require_login
from research_app.components.charts import price_volume_chart
from research_app.components.filters import date_range_picker, symbol_picker
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges

st.set_page_config(page_title="Universe Explorer", page_icon="🔭", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

page_header(
    "Universe Explorer",
    "Daily OHLCV, candles, volume, comparisons.",
    icon="🔭",
)

fc1, fc2 = st.columns([2, 3])
with fc1:
    symbols = symbol_picker(default=["VNM"], max_selections=6)
with fc2:
    start, end = date_range_picker(default_days=180)

if not symbols:
    st.warning("Pick at least one ticker.")
    st.stop()


@st.cache_resource
def _client():
    return vm.Client(env=os.environ.get("ENV", "staging"))


client = _client()


@st.cache_data(ttl=600)
def _daily(syms, s, e) -> pd.DataFrame:
    return client.daily(syms, s, e).to_pandas()


def _fmt_compact(v: float) -> str:
    if v is None or pd.isna(v):
        return "—"
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}"


with st.spinner("Loading daily bars..."):
    df = _daily(symbols, start, end)

if df.empty:
    st.info("No daily rows in this range. Try expanding the date range.")
    st.stop()


# ---------------------------------------------------------------------------
# Compare mode (2-6 symbols): normalized returns + per-symbol metrics
# ---------------------------------------------------------------------------
if len(symbols) > 1:
    st.markdown("### Comparison")
    pivot = df.pivot_table(index="date", columns="symbol", values="close").sort_index()
    if pivot.empty or pivot.shape[1] < 2:
        st.info("Not enough overlapping data to compare.")
    else:
        # Normalize each series to 100 on its first non-null date.
        first_valid = pivot.bfill().iloc[0]
        normed = pivot.divide(first_valid).multiply(100)
        normed_long = normed.reset_index().melt(
            id_vars="date", var_name="symbol", value_name="indexed"
        )
        fig = px.line(
            normed_long,
            x="date",
            y="indexed",
            color="symbol",
            labels={"indexed": "Indexed close (start = 100)"},
        )
        fig.update_layout(
            height=440, hovermode="x unified", margin={"t": 20, "l": 50, "r": 30, "b": 40}
        )
        st.plotly_chart(fig, use_container_width=True)

    # Per-symbol KPI grid
    rows = []
    for sym in symbols:
        sub = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if sub.empty:
            continue
        last = sub.iloc[-1]
        first = sub.iloc[0]
        chg_pct = (last["close"] - first["close"]) / first["close"] * 100
        rets = sub["close"].pct_change().dropna()
        sharpe = (
            (rets.mean() / rets.std() * np.sqrt(252)) if len(rets) > 1 and rets.std() > 0 else 0.0
        )
        peak = sub["close"].cummax()
        mdd = ((sub["close"] - peak) / peak).min() * 100 if len(sub) else 0.0
        rows.append(
            {
                "symbol": sym,
                "last": float(last["close"]),
                "period_pct": float(chg_pct),
                "max_dd_pct": float(mdd),
                "sharpe": float(sharpe),
                "avg_volume": float(sub["volume"].mean()) if "volume" in sub else 0.0,
            }
        )
    if rows:
        kpi_df = pd.DataFrame(rows)
        kpi_df["avg_volume"] = kpi_df["avg_volume"].apply(_fmt_compact)
        st.dataframe(
            kpi_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "symbol": "Symbol",
                "last": st.column_config.NumberColumn("Last", format="%,.0f"),
                "period_pct": st.column_config.NumberColumn("Period %", format="%+.2f%%"),
                "max_dd_pct": st.column_config.NumberColumn("Max DD %", format="%.2f%%"),
                "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
                "avg_volume": "Avg Vol",
            },
        )
    st.stop()


# ---------------------------------------------------------------------------
# Single-symbol mode: candlestick + KPIs + recent rows
# ---------------------------------------------------------------------------
sym = symbols[0]
sub = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
if sub.empty:
    st.info(f"No data for {sym} in range.")
    st.stop()

last = sub.iloc[-1]
first = sub.iloc[0]
chg_pct = (last["close"] - first["close"]) / first["close"] * 100
avg_vol = sub["volume"].mean() if "volume" in sub.columns else 0.0
hi = sub["high"].max() if "high" in sub.columns else sub["close"].max()
lo = sub["low"].min() if "low" in sub.columns else sub["close"].min()

st.markdown(f"### {sym}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Last close", f"{last['close']:,.0f}", f"{chg_pct:+.2f}%")
m2.metric("Period high", f"{hi:,.0f}")
m3.metric("Period low", f"{lo:,.0f}")
m4.metric("Avg volume", _fmt_compact(avg_vol))

st.plotly_chart(price_volume_chart(sub), use_container_width=True)

with st.expander("Recent rows", expanded=False):
    st.dataframe(sub.tail(20), use_container_width=True, hide_index=True)
