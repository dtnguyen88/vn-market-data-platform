"""Streamlit research-app — entrypoint (home).

Run locally:
    streamlit run src/research_app/__main__.py
"""

import streamlit as st

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

page_header(
    "VN Market Research",
    "Vietnam equities lakehouse · daily, ticks, L2, factors",
    icon="📈",
)

# Quick-stats strip (placeholder — wire to live counts later)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Symbols tracked", "30", "core universe")
c2.metric("Years of history", "5y", "vnstock backfill")
c3.metric("Daily rows", "41.6K", "BigLake")
c4.metric("Region", "asia-southeast1", "Singapore")

st.markdown("### Explore")
cards = [
    ("🔭", "Universe Explorer", "Symbol-level daily charts, candles, volume, factor stats."),
    ("🔬", "Microstructure", "Tick tape and L2 order-book snapshots intraday."),
    ("📉", "Backtest Viewer", "Upload an equity-curve CSV/Parquet for stats + chart."),
    ("🧪", "SQL Lab", "Interactive BigQuery editor with auto chart preview."),
]
cols = st.columns(len(cards))
for col, (icon, title, body) in zip(cols, cards, strict=True):
    col.markdown(feature_card(icon, title, body), unsafe_allow_html=True)

st.markdown(
    """<div style="margin-top:2rem; color:#9CA3AF; font-size:.85rem;">
        Pick a page from the left sidebar to begin. Data accessed via the
        <code style="color:#00D4AA;">vnmarket</code> SDK over BigQuery + GCS.
    </div>""",
    unsafe_allow_html=True,
)
