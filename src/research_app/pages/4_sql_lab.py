"""SQL Lab — interactive BigQuery editor with syntax highlighting + auto chart.

Layout: 3-pane.
  Left   = collapsible schema browser + presets + recent history.
  Top    = ace editor with SQL syntax highlighting, line numbers, autocomplete.
  Bottom = results: stats strip, sortable table, CSV download, auto chart.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from google.cloud import bigquery
from research_app.auth import require_login
from research_app.components.theme import apply_theme, page_header, sidebar_env_badges
from streamlit_ace import st_ace

st.set_page_config(page_title="SQL Lab", page_icon="🧪", layout="wide")
apply_theme()
require_login()
sidebar_env_badges()

PROJECT = os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging")
DATASET = "vnmarket"

page_header(
    "SQL Lab",
    f"Interactive BigQuery editor — `{DATASET}`",
    icon="🧪",
)


@st.cache_resource
def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT)


client = _client()


@st.cache_data(ttl=300)
def _list_tables() -> list[tuple[str, int]]:
    """Return [(table_id, row_count_estimate)] sorted by id."""
    rows = []
    for t in client.list_tables(f"{PROJECT}.{DATASET}"):
        try:
            tbl = client.get_table(t)
            rows.append((t.table_id, tbl.num_rows or 0))
        except Exception:
            rows.append((t.table_id, 0))
    return sorted(rows)


@st.cache_data(ttl=600)
def _table_columns(table_id: str) -> list[tuple[str, str]]:
    """Return [(col_name, col_type)] for a table."""
    try:
        tbl = client.get_table(f"{PROJECT}.{DATASET}.{table_id}")
        return [(f.name, f.field_type) for f in tbl.schema]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Sidebar: schema browser + presets + history
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Schema")
    table_filter = st.text_input(
        "Filter tables", placeholder="Type to filter...", label_visibility="collapsed"
    )
    tables = _list_tables()
    if table_filter:
        tables = [(t, n) for t, n in tables if table_filter.lower() in t.lower()]
    for tbl, nrows in tables:
        with st.expander(f"📊 `{tbl}`  ·  {nrows:,} rows"):
            cols = _table_columns(tbl)
            if cols:
                lines = [f"- `{c}` · {t}" for c, t in cols]
                st.markdown("\n".join(lines))
            if st.button(f"Query {tbl}", key=f"sel_{tbl}", use_container_width=True):
                st.session_state["sql"] = (  # table name from cached BQ list
                    f"SELECT *\nFROM `{PROJECT}.{DATASET}.{tbl}`\nLIMIT 100"
                )

    st.markdown("---")
    st.markdown("### Presets")
    presets = {
        "📈 VNM daily 2024": (
            f"SELECT date, symbol, open, high, low, close, volume\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"WHERE symbol = 'VNM' AND date >= '2024-01-01'\n"
            f"ORDER BY date DESC\nLIMIT 250"
        ),
        "🏆 Top volume 30d": (
            f"SELECT symbol, AVG(volume) AS avg_volume, COUNT(*) AS days\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)\n"
            f"GROUP BY symbol\nORDER BY avg_volume DESC\nLIMIT 25"
        ),
        "🗓 Coverage by symbol": (
            f"SELECT symbol, COUNT(*) AS days,\n"
            f"  MIN(date) AS first_date, MAX(date) AS last_date\n"
            f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"GROUP BY symbol\nORDER BY days DESC"
        ),
        "🚀 Best performers YTD": (
            "WITH first_last AS (\n"  # noqa: S608
            f"  SELECT symbol,\n"
            f"    MIN_BY(close, date) AS first_close,\n"
            f"    MAX_BY(close, date) AS last_close\n"
            f"  FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"  WHERE date >= '2026-01-01'\n"
            f"  GROUP BY symbol\n"
            f")\n"
            f"SELECT symbol,\n"
            f"  ROUND((last_close - first_close) / first_close * 100, 2) AS ytd_pct\n"
            f"FROM first_last\nWHERE first_close > 0\nORDER BY ytd_pct DESC\nLIMIT 25"
        ),
        "📉 Biggest drawdown 1y": (
            "WITH ext AS (\n"  # noqa: S608
            f"  SELECT symbol, MAX(close) AS hi, MIN(close) AS lo\n"
            f"  FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
            f"  WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)\n"
            f"  GROUP BY symbol\n"
            f")\n"
            f"SELECT symbol, hi, lo, ROUND((lo - hi) / hi * 100, 2) AS dd_pct\n"
            f"FROM ext\nWHERE hi > 0\nORDER BY dd_pct ASC\nLIMIT 25"
        ),
    }
    for name, q in presets.items():
        if st.button(name, key=f"p_{name}", use_container_width=True):
            st.session_state["sql"] = q

    if st.session_state.get("history"):
        st.markdown("---")
        st.markdown("### Recent")
        for i, item in enumerate(reversed(st.session_state["history"][-5:])):
            preview = item["sql"].split("\n")[0][:40]
            if st.button(f"↻ {preview}", key=f"h_{i}", use_container_width=True):
                st.session_state["sql"] = item["sql"]


# ---------------------------------------------------------------------------
# Main: editor + actions + results
# ---------------------------------------------------------------------------
default_sql = st.session_state.get(
    "sql",
    f"SELECT date, symbol, close, volume\n"
    f"FROM `{PROJECT}.{DATASET}.daily_ohlcv`\n"
    f"WHERE symbol IN ('VNM', 'VIC', 'VHM') AND date >= '2024-01-01'\n"
    f"ORDER BY date DESC\nLIMIT 1000",
)

sql = st_ace(
    value=default_sql,
    language="sql",
    theme="tomorrow_night_eighties",
    keybinding="vscode",
    font_size=14,
    tab_size=2,
    show_gutter=True,
    show_print_margin=False,
    wrap=True,
    auto_update=True,
    min_lines=8,
    max_lines=18,
    placeholder="-- write SQL here · Cmd/Ctrl+Enter to run",
    key="sql_editor",
)

c1, c2, c3, _ = st.columns([2, 2, 2, 6])
run = c1.button("▶ Run", type="primary", use_container_width=True)
clear = c2.button("Clear", use_container_width=True)
fmt_hint = c3.button("Format", use_container_width=True, help="Uppercase keywords")

if clear:
    for k in ("results", "bytes", "elapsed_ms", "error"):
        st.session_state.pop(k, None)

if fmt_hint and sql:
    keywords = ("SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "JOIN", "ON", "AS")
    formatted = sql
    for kw in keywords:
        formatted = formatted.replace(kw, kw.upper())
    st.session_state["sql"] = formatted
    st.rerun()

if run and sql.strip():
    st.session_state.pop("error", None)
    with st.spinner("Running query..."):
        t0 = datetime.utcnow()
        try:
            job = client.query(sql)
            df = job.to_dataframe()
            st.session_state["results"] = df
            st.session_state["bytes"] = job.total_bytes_processed or 0
            st.session_state["elapsed_ms"] = int((datetime.utcnow() - t0).total_seconds() * 1000)
            st.session_state.setdefault("history", []).append(
                {"sql": sql, "rows": len(df), "ts": t0.isoformat()}
            )
        except Exception as exc:
            st.session_state["error"] = str(exc)

if err := st.session_state.get("error"):
    st.error(f"Query failed: {err}")

results: pd.DataFrame | None = st.session_state.get("results")
if results is not None:
    bytes_processed = st.session_state.get("bytes", 0)
    elapsed_ms = st.session_state.get("elapsed_ms", 0)
    cost_usd = bytes_processed / 1e12 * 5  # $5/TiB
    elapsed_disp = f"{elapsed_ms} ms" if elapsed_ms < 1000 else f"{elapsed_ms / 1000:.2f}s"
    bytes_disp = (
        f"{bytes_processed / 1e9:.2f} GB"
        if bytes_processed >= 1e9
        else f"{bytes_processed / 1e6:.1f} MB"
    )
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Rows", f"{len(results):,}")
    s2.metric("Scanned", bytes_disp)
    s3.metric("Cost", f"${cost_usd:.4f}")
    s4.metric("Elapsed", elapsed_disp)

    tab_table, tab_chart = st.tabs(["📋 Table", "📊 Chart"])

    with tab_table:
        st.dataframe(results, use_container_width=True, hide_index=True, height=460)
        st.download_button(
            "⬇ Download CSV",
            data=results.to_csv(index=False).encode("utf-8"),
            file_name=f"query_{datetime.utcnow():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
        )

    with tab_chart:
        if len(results) <= 1:
            st.info("Need at least 2 rows to chart.")
        else:
            date_cols = [c for c in results.columns if "date" in c.lower() or "time" in c.lower()]
            numeric_cols = results.select_dtypes(include="number").columns.tolist()
            cat_cols = [c for c in results.columns if c not in numeric_cols and c not in date_cols]
            x_options = date_cols + cat_cols + numeric_cols
            if not numeric_cols or not x_options:
                st.info("Result has no plottable columns.")
            else:
                cc1, cc2, cc3, cc4 = st.columns(4)
                chart_type = cc1.selectbox("Type", ["line", "bar", "scatter", "histogram"])
                x = cc2.selectbox("X", x_options, index=0)
                y = cc3.selectbox("Y", [c for c in numeric_cols if c != x] or numeric_cols, index=0)
                color_opts = ["(none)"] + [c for c in cat_cols if c != x]
                color = cc4.selectbox("Color", color_opts, index=0)
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
                    fig.update_layout(height=480, margin={"t": 20, "l": 50, "r": 30, "b": 40})
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as exc:
                    st.warning(f"Chart failed: {exc}")
