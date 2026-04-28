"""Backtest Snapshot Viewer — upload CSV/Parquet equity curve."""

from io import BytesIO

import pandas as pd
import streamlit as st
from research_app.components.charts import equity_curve

st.set_page_config(page_title="Backtest Viewer", layout="wide")
st.title("Backtest Snapshot Viewer")

uploaded = st.file_uploader(
    "Upload equity-curve CSV or Parquet (cols: date, equity, [position])",
    type=["csv", "parquet"],
)

if not uploaded:
    st.info("Upload a file to begin.")
    st.stop()

ext = uploaded.name.rsplit(".", 1)[-1].lower()
try:
    if ext == "csv":
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_parquet(BytesIO(uploaded.read()))
except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

required = {"date", "equity"}
missing = required - set(df.columns)
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

st.subheader("Summary stats")
total_ret = df["equity"].iloc[-1] / df["equity"].iloc[0] - 1
peak = df["equity"].cummax()
drawdown = (df["equity"] - peak) / peak
mdd = drawdown.min()
st.metric("Total return", f"{total_ret * 100:.1f}%")
st.metric("Max drawdown", f"{mdd * 100:.1f}%")

st.plotly_chart(equity_curve(df), use_container_width=True)
st.dataframe(df.head(20))
