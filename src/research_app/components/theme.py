"""Shared visual theme: CSS injection, page header, KPI cards, plotly template.

Call `apply_theme()` once near the top of every page (after `set_page_config`,
before any other widgets). Use `page_header()` instead of plain `st.title()` for
a consistent banner on every page.
"""

from __future__ import annotations

import os

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Palette (kept in sync with .streamlit/config.toml)
BG = "#0E1117"
PANEL = "#1A1F2C"
PANEL_2 = "#232938"
ACCENT = "#00D4AA"
ACCENT_DIM = "#0E8F76"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
BULL = "#10B981"
BEAR = "#EF4444"
GRID = "#2A3142"

_CSS = f"""
<style>
  /* ---------- Globals ---------- */
  html, body, [class*="css"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
  }}
  .block-container {{
    padding-top: 1.4rem;
    padding-bottom: 2.5rem;
    max-width: 1400px;
  }}
  /* hide default streamlit chrome */
  #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}

  /* ---------- Sidebar ---------- */
  section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {PANEL} 0%, {BG} 100%);
    border-right: 1px solid {GRID};
  }}
  section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {{ color: {TEXT}; }}

  /* ---------- Buttons ---------- */
  .stButton > button {{
    border-radius: 8px;
    border: 1px solid {GRID};
    background: {PANEL};
    color: {TEXT};
    font-weight: 500;
    transition: all .15s ease;
  }}
  .stButton > button:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
    transform: translateY(-1px);
  }}
  .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DIM} 100%);
    color: {BG};
    border: none;
  }}
  .stButton > button[kind="primary"]:hover {{ color: {BG}; opacity: .92; }}

  /* ---------- Inputs ---------- */
  .stTextInput > div > div > input,
  .stTextArea textarea,
  .stDateInput input,
  .stSelectbox div[data-baseweb="select"] > div {{
    background: {PANEL} !important;
    border: 1px solid {GRID} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
  }}

  /* ---------- DataFrame ---------- */
  div[data-testid="stDataFrame"] {{
    border: 1px solid {GRID};
    border-radius: 10px;
    overflow: hidden;
  }}

  /* ---------- Metric ---------- */
  div[data-testid="stMetric"] {{
    background: {PANEL};
    border: 1px solid {GRID};
    border-radius: 12px;
    padding: .9rem 1rem;
    overflow: hidden;
  }}
  div[data-testid="stMetricLabel"] {{ color: {MUTED}; font-size: .78rem; }}
  div[data-testid="stMetricValue"] {{
    color: {TEXT};
    font-weight: 600;
    font-size: 1.6rem;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  div[data-testid="stMetricDelta"] {{ font-size: .75rem; }}

  /* ---------- Plotly ---------- */
  .js-plotly-plot {{ border-radius: 10px; }}

  /* ---------- Custom classes ---------- */
  .vm-header {{
    background: linear-gradient(135deg, {PANEL} 0%, {BG} 100%);
    border: 1px solid {GRID};
    border-radius: 14px;
    padding: 1.2rem 1.6rem;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }}
  .vm-header .vm-icon {{
    font-size: 2rem;
    background: {PANEL_2};
    border-radius: 12px;
    padding: .4rem .7rem;
    line-height: 1;
  }}
  .vm-header h1 {{
    margin: 0;
    font-size: 1.55rem;
    color: {TEXT};
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  .vm-header p {{ margin: .15rem 0 0; color: {MUTED}; font-size: .92rem; }}

  .vm-card {{
    background: {PANEL};
    border: 1px solid {GRID};
    border-radius: 12px;
    padding: 1.1rem 1.3rem;
    height: 100%;
    transition: border-color .15s ease, transform .15s ease;
  }}
  .vm-card:hover {{ border-color: {ACCENT}; transform: translateY(-2px); }}
  .vm-card .vm-card-icon {{ font-size: 1.6rem; margin-bottom: .4rem; }}
  .vm-card h3 {{ margin: 0 0 .35rem; color: {TEXT}; font-size: 1.05rem; }}
  .vm-card p {{ margin: 0; color: {MUTED}; font-size: .87rem; line-height: 1.45; }}

  .vm-badge {{
    display: inline-block;
    padding: .15rem .55rem;
    border-radius: 999px;
    font-size: .72rem;
    font-weight: 600;
    letter-spacing: .02em;
    text-transform: uppercase;
  }}
  .vm-badge-env {{ background: {ACCENT_DIM}33; color: {ACCENT}; border: 1px solid {ACCENT_DIM}; }}
  .vm-badge-muted {{ background: {PANEL_2}; color: {MUTED}; border: 1px solid {GRID}; }}

  .vm-login-wrap {{
    max-width: 380px;
    margin: 4rem auto 0;
    background: {PANEL};
    border: 1px solid {GRID};
    border-radius: 16px;
    padding: 2rem 2rem 1.5rem;
  }}
  .vm-login-wrap h2 {{ margin: 0 0 .25rem; color: {TEXT}; font-weight: 600; }}
  .vm-login-wrap p {{ color: {MUTED}; font-size: .9rem; margin: 0 0 1.2rem; }}
</style>
"""


def apply_theme() -> None:
    """Inject CSS + register Plotly template. Idempotent per session."""
    st.markdown(_CSS, unsafe_allow_html=True)
    if "vnmarket" not in pio.templates:
        pio.templates["vnmarket"] = go.layout.Template(
            layout=go.Layout(
                font={"family": "Inter, -apple-system, sans-serif", "color": TEXT, "size": 12},
                paper_bgcolor=PANEL,
                plot_bgcolor=PANEL,
                colorway=[ACCENT, "#60A5FA", "#F59E0B", "#A78BFA", "#F472B6", "#34D399"],
                xaxis={"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID},
                yaxis={"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID},
                legend={"bgcolor": "rgba(0,0,0,0)", "bordercolor": GRID, "borderwidth": 1},
                margin={"l": 50, "r": 30, "t": 50, "b": 40},
                hoverlabel={"bgcolor": PANEL_2, "bordercolor": ACCENT, "font_color": TEXT},
            )
        )
    pio.templates.default = "vnmarket"


def page_header(title: str, subtitle: str = "", icon: str = "📊") -> None:
    """Render the standard page header banner."""
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""<div class="vm-header">
            <div class="vm-icon">{icon}</div>
            <div><h1>{title}</h1>{sub_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def feature_card(icon: str, title: str, body: str) -> str:
    """Return HTML for a feature card (use inside a column block)."""
    return (
        f'<div class="vm-card"><div class="vm-card-icon">{icon}</div>'
        f"<h3>{title}</h3><p>{body}</p></div>"
    )


_NAV_PAGES: list[tuple[str, str, str]] = [
    ("__main__.py", "Home", "🏠"),
    ("pages/1_universe_explorer.py", "Universe Explorer", "🔭"),
    ("pages/5_market_movers.py", "Market Movers", "🚀"),
    ("pages/2_microstructure.py", "Microstructure", "🔬"),
    ("pages/3_backtest_viewer.py", "Backtest Viewer", "📉"),
    ("pages/4_sql_lab.py", "SQL Lab", "🧪"),
]


def render_sidebar_nav() -> None:
    """Render the custom sidebar nav (replaces Streamlit's auto-generated list).

    Streamlit's default uses lowercase filename labels. We disable it via
    .streamlit/config.toml `showSidebarNavigation = false` and render proper
    labels + icons here.
    """
    st.sidebar.markdown(
        f"""<div style="font-size:.7rem; color:{MUTED}; letter-spacing:.08em;
        text-transform:uppercase; margin: .2rem 0 .4rem .25rem;">Navigate</div>""",
        unsafe_allow_html=True,
    )
    for path, label, icon in _NAV_PAGES:
        st.sidebar.page_link(path, label=label, icon=icon)
    st.sidebar.markdown("---")


def sidebar_env_badges() -> None:
    """Render the standard sidebar header (nav + env + project)."""
    render_sidebar_nav()
    env = os.environ.get("ENV", "staging")
    project = os.environ.get("GCP_PROJECT_ID", "(unset)")
    st.sidebar.markdown(
        f"""<div style="margin-bottom: .8rem;">
            <span class="vm-badge vm-badge-env">{env}</span>
            <div style="margin-top: .5rem; color:{MUTED}; font-size:.78rem;">
                <code style="background:transparent; color:{MUTED};">{project}</code>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
