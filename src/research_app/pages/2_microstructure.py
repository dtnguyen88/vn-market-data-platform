"""Microstructure Inspector — tick tape + L2 snapshot."""

import os
from datetime import datetime

import streamlit as st
import vnmarket as vm
from research_app.auth import require_login
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges

st.set_page_config(page_title="Microstructure", page_icon="🔬", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

page_header(
    "Microstructure Inspector",
    "Intraday tick tape + L2 order-book snapshot.",
    icon="🔬",
)


@st.cache_resource
def _client():
    return vm.Client(env=os.environ.get("ENV", "staging"))


client = _client()

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    symbol = st.text_input("Symbol", value="VNM").upper()
with c2:
    on_date = st.date_input("Date", value=datetime.utcnow().date())
with c3:
    ts_str = st.text_input(
        "L2 snapshot timestamp (ISO 8601)",
        value=f"{on_date.isoformat()}T10:00:00+07:00",
    )

if not (symbol and on_date):
    st.stop()

left, right = st.columns([3, 2])

with left:
    st.markdown("#### Tick tape (latest 50)")
    try:
        ticks = client.ticks(symbol, on_date).collect().to_pandas().tail(50)
        if ticks.empty:
            st.info("No ticks found for this symbol/date.")
        else:
            st.dataframe(ticks, use_container_width=True, hide_index=True, height=520)
    except Exception as e:
        st.warning(f"No ticks available: {e}")

with right:
    st.markdown("#### L2 book (top 10)")
    try:
        book = client.l2_at(symbol, ts_str)
        bid_px = book.get("bid_px") or []
        ask_px = book.get("ask_px") or []
        if not any(bid_px) and not any(ask_px):
            st.info("No L2 snapshot at-or-before this timestamp.")
        else:
            import pandas as pd

            rows = []
            for i in range(10):
                rows.append(
                    {
                        "Lvl": i + 1,
                        "Bid sz": (book.get("bid_sz") or [None] * 10)[i],
                        "Bid px": (bid_px or [None] * 10)[i],
                        "Ask px": (ask_px or [None] * 10)[i],
                        "Ask sz": (book.get("ask_sz") or [None] * 10)[i],
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=520)
    except Exception as e:
        st.warning(f"L2 unavailable: {e}")
