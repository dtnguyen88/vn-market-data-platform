"""Market Movers — top gainers, losers, and volume leaders across the lake.

Single BigQuery scan returns the latest trading day's close + prior-day close
for every symbol, then ranks by % change and absolute volume. Lookback window
controls the reference date (1d, 5d, 30d, YTD).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from research_app.auth import require_login
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges

st.set_page_config(page_title="Market Movers", page_icon="🚀", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

PROJECT = os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging")
DATASET = "vnmarket"

page_header(
    "Market Movers",
    "Top gainers, losers, and volume leaders across the Vietnam universe.",
    icon="🚀",
)


@st.cache_resource
def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT)


client = _client()

c1, c2, c3 = st.columns([1, 1, 4])
with c1:
    lookback = st.selectbox(
        "Window",
        options=[("1 day", 1), ("5 days", 5), ("1 month", 30), ("3 months", 90), ("YTD", -1)],
        format_func=lambda x: x[0],
        index=0,
    )
with c2:
    min_avg_vol = st.number_input(
        "Min avg volume", min_value=0, value=10000, step=1000, help="Filter out illiquid names"
    )
with c3:
    top_n = st.slider("Top N", 5, 50, 15)

interval_days = lookback[1]


@st.cache_data(ttl=300)
def _movers(interval_days: int, min_vol: int) -> pd.DataFrame:
    if interval_days == -1:
        # YTD
        ref_clause = "DATE(EXTRACT(YEAR FROM CURRENT_DATE()), 1, 1)"
    else:
        ref_clause = f"DATE_SUB(latest_d, INTERVAL {interval_days} DAY)"
    sql = f"""
    WITH last_ts AS (
      SELECT MAX(date) AS latest_d FROM `{PROJECT}.{DATASET}.daily_ohlcv`
    ),
    bracket AS (
      SELECT s.symbol,
        ARRAY_AGG(STRUCT(s.date, s.close, s.volume)
          ORDER BY s.date DESC LIMIT 1)[OFFSET(0)] AS last_row,
        ARRAY_AGG(STRUCT(s.date, s.close, s.volume)
          ORDER BY s.date ASC LIMIT 1)[OFFSET(0)] AS first_row,
        AVG(s.volume) AS avg_vol
      FROM `{PROJECT}.{DATASET}.daily_ohlcv` s, last_ts
      WHERE s.date BETWEEN {ref_clause} AND latest_d
      GROUP BY s.symbol
    )
    SELECT
      symbol,
      last_row.date AS last_date,
      last_row.close AS last_close,
      first_row.close AS ref_close,
      last_row.volume AS last_volume,
      avg_vol,
      ROUND((last_row.close - first_row.close) / NULLIF(first_row.close, 0) * 100, 2) AS pct_change
    FROM bracket
    WHERE avg_vol >= {min_vol}
      AND first_row.close > 0
    ORDER BY pct_change DESC
    """  # noqa: S608
    return client.query(sql).to_dataframe()


with st.spinner("Scanning universe..."):
    df = _movers(interval_days, int(min_avg_vol))

if df.empty:
    st.info("No movers found. Try lowering 'min avg volume' or pick a longer window.")
    st.stop()

# Header strip
m1, m2, m3, m4 = st.columns(4)
m1.metric("Symbols", f"{len(df):,}")
m2.metric("Latest date", str(df["last_date"].max())[:10])
gainers = (df["pct_change"] > 0).sum()
losers = (df["pct_change"] < 0).sum()
m3.metric("Gainers", f"{gainers:,}")
m4.metric("Losers", f"{losers:,}")

tab_g, tab_l, tab_v = st.tabs(["📈 Top Gainers", "📉 Top Losers", "💵 Volume Leaders"])


def _format_table(df: pd.DataFrame) -> None:
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "symbol": "Symbol",
            "last_date": "Date",
            "last_close": st.column_config.NumberColumn("Close (kVND)", format="%,.2f"),
            "ref_close": st.column_config.NumberColumn("Ref close (kVND)", format="%,.2f"),
            "pct_change": st.column_config.NumberColumn("% chg", format="%+.2f%%"),
            "last_volume": st.column_config.NumberColumn("Last vol", format="%,.0f"),
            "avg_vol": st.column_config.NumberColumn("Avg vol", format="%,.0f"),
        },
    )


with tab_g:
    _format_table(df.nlargest(top_n, "pct_change"))

with tab_l:
    _format_table(df.nsmallest(top_n, "pct_change"))

with tab_v:
    _format_table(df.nlargest(top_n, "avg_vol"))
