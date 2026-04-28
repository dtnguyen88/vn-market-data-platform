"""Reusable Plotly chart factories for research-app."""

import plotly.graph_objects as go


def price_volume_chart(df, title: str = "Price + Volume") -> go.Figure:
    """Two-panel: close price (top) + volume bars (bottom). df has date, close, volume."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["close"], name="close", yaxis="y1"))
    fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="volume", yaxis="y2", opacity=0.4))
    fig.update_layout(
        title=title,
        yaxis={"title": "close (1/10 VND)"},
        yaxis2={"title": "volume", "overlaying": "y", "side": "right"},
        hovermode="x unified",
        height=500,
    )
    return fig


def equity_curve(df, title: str = "Equity Curve") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["equity"], name="equity"))
    fig.update_layout(title=title, hovermode="x", height=400)
    return fig
