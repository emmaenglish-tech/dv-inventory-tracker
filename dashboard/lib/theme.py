"""Shared visual identity: one registered Plotly template + named colors.

Centralizing this means every chart in the app is consistent and a palette
change is a one-file edit. Charts reference the semantic dicts
(``INSTRUMENT_COLORS`` etc.) rather than hard-coding hex values.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# Warm, professional palette for a violin shop (wood / sage / slate).
BROWN = "#9A6A43"
SAGE = "#7A9E7E"
SLATE = "#5B7B9A"
GOLD = "#C8943C"
WINE = "#9E4B3B"
WARM_GRAY = "#B7AEA1"
INK = "#2B2B2B"
PANEL = "#F5F1EA"

INSTRUMENT_COLORS = {
    "violin": GOLD,
    "viola": SAGE,
    "cello": SLATE,
    "bass": "#6B5B95",
    "unknown": WARM_GRAY,
}

# Owned / Rented / Available / Delinquent — used by the inventory state charts.
STATE_COLORS = {
    "Owned": SLATE,
    "Rented": BROWN,
    "Available": SAGE,
    "Delinquent": WINE,
}

SCOPE_COLORS = {  # high-end vs regular
    "High-End": BROWN,
    "Regular": SLATE,
}

_TEMPLATE_NAME = "denver_violins"


def _build_template() -> go.layout.Template:
    return go.layout.Template(
        layout=go.Layout(
            colorway=[BROWN, SLATE, SAGE, GOLD, WINE, WARM_GRAY],
            font=dict(family="sans serif", color=INK, size=13),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            title=dict(font=dict(size=17, color=INK), x=0.0, xanchor="left"),
            margin=dict(l=60, r=30, t=60, b=50),
            xaxis=dict(showgrid=False, linecolor="#D9D2C6", ticks="outside",
                       tickcolor="#D9D2C6"),
            yaxis=dict(gridcolor="#ECE6DA", zerolinecolor="#D9D2C6"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0, title_text=""),
            hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D9D2C6",
                            font=dict(color=INK)),
        )
    )


def apply_theme() -> None:
    """Register + activate the shared template. Call once per page."""
    pio.templates[_TEMPLATE_NAME] = _build_template()
    pio.templates.default = _TEMPLATE_NAME
