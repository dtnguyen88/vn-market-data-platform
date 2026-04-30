"""Universe Explorer — symbol-level daily charts + fundamentals."""

import os

import streamlit as st
import vnmarket as vm
from research_app.auth import require_login
from research_app.components.charts import price_volume_chart
from research_app.components.filters import date_range_picker, symbol_picker

st.set_page_config(page_title="Universe Explorer", layout="wide")
require_login()
st.title("Universe Explorer")

symbols = symbol_picker(default=["VNM"])
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


df = _daily(symbols, start, end)
if df.empty:
    st.info("No daily rows in range.")
else:
    for sym in symbols:
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        st.subheader(sym)
        st.plotly_chart(price_volume_chart(sub, title=sym), use_container_width=True)
        st.dataframe(sub.tail(10))
