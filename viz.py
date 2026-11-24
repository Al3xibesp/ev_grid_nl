"""Plotly helpers: one visual system for every chart in the app.

Rules applied (dataviz skill): thin marks, recessive grid, one y-axis per chart,
colour follows the entity (BEV blue, PHEV orange, HEV aqua everywhere), a legend
whenever there are two or more series plus direct end-labels, events annotated.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from pipeline.config import COLORS, EVENTS

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
AXIS = "#c3c2b7"

# non-technology categorical slots (kept off blue/orange/aqua so they never impersonate BEV/PHEV/HEV)
STATE_COLORS = ["#6250d6", "#e87ba4", "#008300", "#eda100", "#e34948"]
NL_COLOR = COLORS["ink"]


def style(fig: go.Figure, height: int = 380, ytitle: str | None = None, xtitle: str | None = None,
          legend: bool = True, hover: str = "x unified") -> go.Figure:
    fig.update_layout(
        template=None, height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=COLORS["ink2"]),
        margin=dict(l=8, r=8, t=28, b=8), hovermode=hover, showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    font=dict(size=12)),
        hoverlabel=dict(font=dict(family=FONT, size=12), bgcolor="#fcfcfb", bordercolor=AXIS),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS, title=xtitle,
                     zeroline=False)
    fig.update_yaxes(gridcolor=COLORS["gridline"], gridwidth=1, zeroline=False, title=ytitle,
                     linecolor="rgba(0,0,0,0)")
    return fig


def line(fig: go.Figure, x, y, name: str, color: str, width: float = 2, dash: str | None = None,
         fmt: str = ",.0f", unit: str = "", showlegend: bool = True, opacity: float = 1.0) -> None:
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name, mode="lines", line=dict(color=color, width=width, dash=dash),
        opacity=opacity, showlegend=showlegend, connectgaps=False,
        hovertemplate=f"%{{y:{fmt}}}{unit}<extra>{name}</extra>"))


def end_label(fig: go.Figure, x, y, text: str, color: str | None = None, dx: int = 6) -> None:
    """Direct label at the last point of a line (text stays in ink, a dot carries the colour)."""
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", xshift=dx,
                       font=dict(size=12, color=COLORS["ink2"]))


def _in_range(date, lo, hi) -> bool:
    return pd.Timestamp(lo) <= pd.Timestamp(date) <= pd.Timestamp(hi)


def add_event(fig: go.Figure, key: str, lo, hi, level: int = 0, label: str | None = None) -> None:
    """Dashed vertical marker with a label; `level` staggers labels so they do not collide."""
    ev = EVENTS[key]
    if not _in_range(ev["date"], lo, hi):
        return
    fig.add_shape(type="line", x0=ev["date"], x1=ev["date"], y0=0, y1=1, yref="paper",
                  line=dict(color=COLORS["muted"], width=1, dash="dot"), layer="below")
    fig.add_annotation(x=ev["date"], y=1 - 0.075 * level, yref="paper", text=label or ev["label"],
                       showarrow=False, xanchor="left", yanchor="top", xshift=4,
                       font=dict(size=11, color=COLORS["ink2"]), bgcolor="rgba(249,249,247,0.85)")


def add_band(fig: go.Figure, key_start: str, key_end: str, lo, hi, label: str, level: int = 0) -> None:
    a, b = EVENTS[key_start]["date"], EVENTS[key_end]["date"]
    a, b = max(pd.Timestamp(a), pd.Timestamp(lo)), min(pd.Timestamp(b), pd.Timestamp(hi))
    if a >= b:
        return
    fig.add_shape(type="rect", x0=a, x1=b, y0=0, y1=1, yref="paper", line=dict(width=0),
                  fillcolor="rgba(137,135,129,0.13)", layer="below")
    fig.add_annotation(x=a, y=1 - 0.075 * level, yref="paper", text=label, showarrow=False,
                       xanchor="left", yanchor="top", xshift=4,
                       font=dict(size=11, color=COLORS["ink2"]), bgcolor="rgba(249,249,247,0.85)")
