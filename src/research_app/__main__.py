"""Streamlit research-app — entrypoint.

Run locally:
    streamlit run src/research_app/__main__.py

Cloud Run:
    streamlit run --server.port=$PORT --server.address=0.0.0.0 ...
"""

import os

import streamlit as st

st.set_page_config(
    page_title="VN Market Research",
    page_icon=":bar_chart:",
    layout="wide",
)

st.title("VN Market Research")
st.write("Welcome. Use the left sidebar to navigate to a page.")
st.sidebar.markdown("**Env:** " + os.environ.get("ENV", "staging"))
st.sidebar.markdown("**Project:** " + os.environ.get("GCP_PROJECT_ID", "(unset)"))

st.markdown(
    """
    ## Pages

    - **Universe Explorer** — Symbol-level daily charts + fundamentals + factor stats.
    - **Microstructure Inspector** — Tick tape + L2 evolution heatmap.
    - **Backtest Snapshot Viewer** — Upload a CSV/Parquet of equity curve and explore.

    Data access: `vnmarket` SDK, project = ENV-prefixed.
    """
)
