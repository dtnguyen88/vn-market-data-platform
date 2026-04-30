"""Universe Explorer — symbol-level daily charts + summary stats."""

import os

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
    "Symbol-level daily candles, volume, and quick stats.",
    icon="🔭",
)

with st.container():
    fc1, fc2 = st.columns([2, 3])
    with fc1:
        symbols = symbol_picker(default=["VNM"])
    with fc2:
        start, end = date_range_picker()

if not symbols:
    st.warning("Enter at least one symbol.")
    st.stop()


@st.cache_resource
def _client():
    return vm.Client(env=os.environ.get("ENV", "staging"))


client = _client()


@st.cache_data(ttl=600)
def _daily(syms, s, e):
    return client.daily(syms, s, e).to_pandas()


with st.spinner("Loading daily bars..."):
    df = _daily(symbols, start, end)

if df.empty:
    st.info("No daily rows in range.")
    st.stop()

for sym in symbols:
    sub = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
    if sub.empty:
        st.markdown(f"**{sym}** — no data.")
        continue

    st.markdown(f"### {sym}")
    last = sub.iloc[-1]
    first = sub.iloc[0]
    chg_pct = (last["close"] - first["close"]) / first["close"] * 100
    avg_vol = sub["volume"].mean()
    hi = sub["high"].max() if "high" in sub.columns else sub["close"].max()
    lo = sub["low"].min() if "low" in sub.columns else sub["close"].min()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Last close", f"{last['close']:,.0f}", f"{chg_pct:+.2f}% range")
    m2.metric("Period high", f"{hi:,.0f}")
    m3.metric("Period low", f"{lo:,.0f}")
    m4.metric("Avg volume", f"{avg_vol:,.0f}")

    st.plotly_chart(price_volume_chart(sub), use_container_width=True)
    with st.expander("Recent rows", expanded=False):
        st.dataframe(sub.tail(10), use_container_width=True, hide_index=True)
