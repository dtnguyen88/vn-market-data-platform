"""SQL Lab — interactive BigQuery explorer with auto chart preview.

Features:
- Sidebar table picker (lists all tables in vnmarket dataset).
- Multi-line SQL editor with example snippets.
- Run query → results as dataframe + auto-detected chart preview.
- Download results as CSV.
"""

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from google.cloud import bigquery
from research_app.auth import require_login
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges

st.set_page_config(page_title="SQL Lab", page_icon="🧪", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

page_header(
    "SQL Lab",
    "Interactive BigQuery — query the lake, chart the result.",
    icon="🧪",
)

PROJECT = os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging")
DATASET = "vnmarket"


@st.cache_resource
def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT)


client = _client()


@st.cache_data(ttl=300)
def _list_tables() -> list[str]:
    return [t.table_id for t in client.list_tables(f"{PROJECT}.{DATASET}")]


# Sidebar: schema browser
with st.sidebar:
    st.markdown(f"**Project:** `{PROJECT}`")
    st.markdown(f"**Dataset:** `{DATASET}`")
    st.markdown("---")
    st.markdown("**Tables:**")
    for tbl in _list_tables():
        st.code(f"{DATASET}.{tbl}", language=None)

    st.markdown("---")
    st.markdown("**Example queries:**")
    examples = {
        "VNM daily 2024": (
            f"SELECT date, symbol, open, high, low, close, volume\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"WHERE symbol = 'VNM' AND date >= '2024-01-01'\n"
            f"ORDER BY date DESC\nLIMIT 250"
        ),
        "Top volume 30d": (
            f"SELECT symbol, AVG(volume) AS avg_volume\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)\n"
            f"GROUP BY symbol\nORDER BY avg_volume DESC\nLIMIT 20"
        ),
        "Symbols & date range": (
            f"SELECT symbol, COUNT(*) AS days,\n"
            f"  MIN(date) AS first_date, MAX(date) AS last_date\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"GROUP BY symbol\nORDER BY symbol"
        ),
        "Best performers YTD": (
            "WITH first_last AS (\n"  # noqa: S608  static example template, not executed
            f"  SELECT symbol,\n"
            f"    MIN_BY(close, date) AS open_close,\n"
            f"    MAX_BY(close, date) AS close_close\n"
            f"  FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"  WHERE date >= '2026-01-01'\n"
            f"  GROUP BY symbol\n"
            f")\n"
            f"SELECT symbol,\n"
            f"  ROUND((close_close - open_close) / open_close * 100, 2) AS ytd_return_pct\n"
            f"FROM first_last\nORDER BY ytd_return_pct DESC"
        ),
    }
    for name, q in examples.items():
        if st.button(name, use_container_width=True):
            st.session_state["sql"] = q


# Main: query editor + results
default_sql = st.session_state.get(
    "sql",
    f"SELECT date, symbol, close, volume\n"
    f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
    f"WHERE symbol IN ('VNM', 'VIC', 'VHM') AND date >= '2024-01-01'\n"
    f"ORDER BY date DESC\nLIMIT 1000",
)
sql = st.text_area("SQL", value=default_sql, height=180, key="sql_editor")

col1, col2, _ = st.columns([1, 1, 6])
run = col1.button("Run", type="primary")
clear = col2.button("Clear results")

if clear and "results" in st.session_state:
    del st.session_state["results"]

if run:
    with st.spinner("Running query..."):
        try:
            job = client.query(sql)
            df = job.to_dataframe()
            st.session_state["results"] = df
            st.session_state["bytes"] = job.total_bytes_processed or 0
        except Exception as exc:
            st.error(f"Query failed: {exc}")

results: pd.DataFrame | None = st.session_state.get("results")
if results is not None:
    bytes_processed = st.session_state.get("bytes", 0)
    st.caption(
        f"{len(results):,} rows · {bytes_processed / 1e6:.1f} MB processed"
        f" · ~${bytes_processed / 1e12 * 5:.4f} estimated cost"
    )
    st.dataframe(results, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV",
        data=results.to_csv(index=False).encode("utf-8"),
        file_name="query.csv",
        mime="text/csv",
    )

    # Auto chart preview: pick a date/x col + numeric y col(s)
    if len(results) > 1:
        st.markdown("### Chart")
        date_cols = [c for c in results.columns if "date" in c.lower() or "time" in c.lower()]
        numeric_cols = results.select_dtypes(include="number").columns.tolist()
        cat_cols = [c for c in results.columns if c not in numeric_cols and c not in date_cols]

        chart_types = ["line", "bar", "scatter", "histogram"]
        chart_type = st.selectbox("Chart type", chart_types, index=0)
        c1, c2, c3 = st.columns(3)
        x_options = date_cols + cat_cols + numeric_cols
        if not x_options:
            st.info("No plottable columns.")
        else:
            x = c1.selectbox("X axis", x_options, index=0)
            y = c2.selectbox("Y axis", [c for c in numeric_cols if c != x] or numeric_cols, index=0)
            color_opts = ["(none)"] + [c for c in cat_cols if c != x]
            color = c3.selectbox("Color (group)", color_opts, index=0)
            color_arg = None if color == "(none)" else color

            try:
                if chart_type == "line":
                    fig = px.line(results, x=x, y=y, color=color_arg)
                elif chart_type == "bar":
                    fig = px.bar(results, x=x, y=y, color=color_arg)
                elif chart_type == "scatter":
                    fig = px.scatter(results, x=x, y=y, color=color_arg)
                else:
                    fig = px.histogram(results, x=y, color=color_arg)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as exc:
                st.warning(f"Chart failed: {exc}")
