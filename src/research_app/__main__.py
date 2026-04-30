"""Streamlit research-app — entrypoint (home)."""

import os

import streamlit as st
from google.cloud import bigquery

from research_app.auth import require_login
from research_app.components.theme import (
    apply_theme,
    feature_card,
    page_header,
    sidebar_env_badges,
)

st.set_page_config(
    page_title="VN Market Research",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()
require_login()
sidebar_env_badges()

PROJECT = os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging")
DATASET = "vnmarket"


@st.cache_resource
def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT)


@st.cache_data(ttl=600)
def _stats() -> dict:
    """Lake stats — single BQ query, cached 10 min."""
    try:
        sql = (
            f"SELECT COUNT(*) AS row_count, COUNT(DISTINCT symbol) AS symbol_count, "  # noqa: S608
            f"MIN(date) AS first_date, MAX(date) AS last_date "
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`"
        )
        row = next(iter(_client().query(sql).result()))
        return {
            "rows": int(row["row_count"] or 0),
            "symbols": int(row["symbol_count"] or 0),
            "first_date": str(row["first_date"]) if row["first_date"] else "—",
            "last_date": str(row["last_date"]) if row["last_date"] else "—",
        }
    except Exception:
        return {"rows": 0, "symbols": 0, "first_date": "—", "last_date": "—"}


page_header(
    "VN Market Research",
    "Vietnam equities lakehouse · daily, ticks, L2, factors",
    icon="📈",
)


def _fmt_compact(v: int) -> str:
    if v >= 1e9:
        return f"{v / 1e9:.2f}B"
    if v >= 1e6:
        return f"{v / 1e6:.2f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:,}"


def _fmt_short_date(s: str) -> str:
    """2024-04-22 -> Apr '24; falls back to original on parse error."""
    try:
        from datetime import datetime as _dt

        d = _dt.strptime(s, "%Y-%m-%d")
        return d.strftime("%b '%y")
    except Exception:
        return s


stats = _stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Symbols", f"{stats['symbols']:,}")
c2.metric("Rows", _fmt_compact(stats["rows"]))
c3.metric("From", _fmt_short_date(stats["first_date"]))
c4.metric("To", _fmt_short_date(stats["last_date"]))
st.caption(
    f"Range: {stats['first_date']} → {stats['last_date']}  ·  "
    f"{stats['symbols']:,} symbols  ·  {stats['rows']:,} rows"
)

st.markdown("### Explore")
cards = [
    ("🔭", "Universe Explorer", "Symbol charts, candles, multi-symbol comparison."),
    ("🚀", "Market Movers", "Top gainers, losers, and volume leaders."),
    ("🧪", "SQL Lab", "Interactive BigQuery editor with auto chart."),
    ("🔬", "Microstructure", "Tick tape and L2 order-book snapshots."),
    ("📉", "Backtest Viewer", "Upload an equity-curve CSV/Parquet."),
]
# 3-up grid: avoids the 5-column squeeze that wraps single words.
for row_start in range(0, len(cards), 3):
    cols = st.columns(3)
    for col, (icon, title, body) in zip(cols, cards[row_start : row_start + 3], strict=False):
        col.markdown(feature_card(icon, title, body), unsafe_allow_html=True)
    if row_start + 3 < len(cards):
        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)

st.markdown(
    """<div style="margin-top:2rem; color:#9CA3AF; font-size:.85rem;">
        Pick a page from the left sidebar to begin. Data accessed via the
        <code style="color:#00D4AA;">vnmarket</code> SDK over BigQuery + GCS.
    </div>""",
    unsafe_allow_html=True,
)
