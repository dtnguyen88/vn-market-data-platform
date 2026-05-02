"""Reusable Plotly chart factories for research-app.

Uses the `vnmarket` Plotly template registered in components/theme.py.
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

BULL = "#10B981"
BEAR = "#EF4444"
ACCENT = "#00D4AA"


def price_volume_chart(df, title: str = "") -> go.Figure:
    """Two-panel: candlestick (top, 75%) + volume bars (bottom, 25%).

    df cols: date, open, high, low, close, volume.
    Falls back to a line chart if open/high/low are absent.
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25]
    )
    has_ohlc = {"open", "high", "low"}.issubset(df.columns)
    if has_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                increasing_line_color=BULL,
                decreasing_line_color=BEAR,
                increasing_fillcolor=BULL,
                decreasing_fillcolor=BEAR,
                name="OHLC",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["close"], name="close", line={"color": ACCENT, "width": 2}
            ),
            row=1,
            col=1,
        )

    if "volume" in df.columns:
        colors = [
            BULL if c >= o else BEAR
            for c, o in zip(df["close"], df.get("open", df["close"]), strict=False)
        ]
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["volume"],
                name="volume",
                marker_color=colors,
                opacity=0.65,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    layout_kwargs = {
        "height": 520,
        "hovermode": "x unified",
        "xaxis_rangeslider_visible": False,
        "showlegend": False,
        "margin": {"l": 50, "r": 30, "t": 30 if title else 10, "b": 40},
    }
    if title:
        layout_kwargs["title"] = title
    fig.update_layout(**layout_kwargs)
    fig.update_yaxes(title_text="Price (kVND)", row=1, col=1)
    fig.update_yaxes(title_text="Volume (shares)", row=2, col=1)
    return fig


def equity_curve(df, title: str = "Equity curve") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["equity"],
            name="equity",
            line={"color": ACCENT, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(0, 212, 170, 0.08)",
        )
    )
    fig.update_layout(title=title, hovermode="x", height=420, showlegend=False)
    return fig
