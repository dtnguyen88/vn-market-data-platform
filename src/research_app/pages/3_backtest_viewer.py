"""Backtest Snapshot Viewer — upload CSV/Parquet equity curve."""

from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st
from research_app.auth import require_login
from research_app.components.charts import equity_curve
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges

st.set_page_config(page_title="Backtest Viewer", page_icon="📉", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

page_header(
    "Backtest Snapshot Viewer",
    "Upload an equity curve (CSV/Parquet) — get stats + chart.",
    icon="📉",
)

uploaded = st.file_uploader(
    "Equity-curve file. Required columns: `date`, `equity`. Optional: `position`.",
    type=["csv", "parquet"],
)

if not uploaded:
    st.info("Drop a file above to begin.")
    st.stop()

ext = uploaded.name.rsplit(".", 1)[-1].lower()
try:
    df = pd.read_csv(uploaded) if ext == "csv" else pd.read_parquet(BytesIO(uploaded.read()))
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

missing = {"date", "equity"} - set(df.columns)
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

total_ret = df["equity"].iloc[-1] / df["equity"].iloc[0] - 1
peak = df["equity"].cummax()
drawdown = (df["equity"] - peak) / peak
mdd = drawdown.min()

rets = df["equity"].pct_change().dropna()
sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
days = (df["date"].iloc[-1] - df["date"].iloc[0]).days or 1
cagr = (1 + total_ret) ** (365 / days) - 1

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total return", f"{total_ret * 100:.1f}%")
m2.metric("CAGR", f"{cagr * 100:.1f}%")
m3.metric("Max drawdown", f"{mdd * 100:.1f}%")
m4.metric("Sharpe (252)", f"{sharpe:.2f}")

st.plotly_chart(equity_curve(df), use_container_width=True)
with st.expander("Preview rows", expanded=False):
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
