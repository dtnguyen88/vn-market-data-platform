"""Reusable Streamlit filter widgets."""

from __future__ import annotations

import os
from datetime import date, timedelta

import streamlit as st
from google.cloud import bigquery


@st.cache_resource
def _bq() -> bigquery.Client:
    return bigquery.Client(project=os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging"))


@st.cache_data(ttl=3600)
def _all_symbols() -> list[str]:
    """Distinct symbols from daily_ohlcv for autocomplete. Cached for an hour."""
    project = os.environ.get("GCP_PROJECT_ID", "vn-market-platform-staging")
    try:
        rows = (
            _bq()
            .query(
                f"SELECT DISTINCT symbol FROM `{project}.vnmarket.daily_ohlcv` "  # noqa: S608
                f"WHERE symbol IS NOT NULL ORDER BY symbol"
            )
            .result()
        )
        return [r["symbol"] for r in rows]
    except Exception:
        return []


def symbol_picker(
    label: str = "Symbols", default: list[str] | None = None, max_selections: int | None = None
) -> list[str]:
    """Multi-select symbol picker with autocomplete from BigQuery universe."""
    options = _all_symbols()
    if not options:
        # fallback to free-text if BQ unavailable
        raw = st.text_input(label, value=",".join(default or ["VNM"]))
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    return st.multiselect(
        label,
        options=options,
        default=default or ["VNM"],
        max_selections=max_selections,
        placeholder="Search by ticker (e.g. VNM)...",
    )


def date_range_picker(default_days: int = 90) -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=default_days)
    s, e = st.date_input("Date range", value=(start, end))
    return s, e
