"""Microstructure Inspector — tick tape + L2 snapshot."""

import os
from datetime import datetime

import streamlit as st
import vnmarket as vm
from research_app.auth import require_login

st.set_page_config(page_title="Microstructure Inspector", layout="wide")
require_login()
st.title("Microstructure Inspector")


@st.cache_resource
def _client():
    return vm.Client(env=os.environ.get("ENV", "staging"))


client = _client()

symbol = st.text_input("Symbol", value="VNM").upper()
on_date = st.date_input("Date", value=datetime.utcnow().date())
ts_str = st.text_input(
    "Snapshot timestamp (ISO 8601, used by L2)",
    value=f"{on_date.isoformat()}T10:00:00+07:00",
)

if symbol and on_date:
    st.subheader("Tick tape (latest 50)")
    try:
        ticks = client.ticks(symbol, on_date).collect().to_pandas().tail(50)
        st.dataframe(ticks)
    except Exception as e:
        st.warning(f"No ticks available: {e}")

    st.subheader("L2 book (top 10)")
    try:
        book = client.l2_at(symbol, ts_str)
        st.json(dict(book))
    except Exception as e:
        st.warning(f"L2 unavailable: {e}")
