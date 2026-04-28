"""Reusable Streamlit filter widgets."""

from datetime import date, timedelta

import streamlit as st


def symbol_picker(label: str = "Symbols", default: list[str] | None = None) -> list[str]:
    """Multi-select symbol picker (free-text)."""
    raw = st.text_input(label, value=",".join(default or ["VNM", "VIC"]))
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def date_range_picker(default_days: int = 90) -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=default_days)
    s, e = st.date_input("Date range", value=(start, end))
    return s, e
