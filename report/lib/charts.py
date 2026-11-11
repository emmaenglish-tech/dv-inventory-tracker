"""Plotly figures for the report. Drawing only: every value comes straight from an rpt_* row.

Visual rules (validated palette; see the dataviz notes in README.md):
* Categorical colors follow the entity, in a fixed order per dimension (never cycled, max 8);
  "not recorded" / "other" buckets are neutral gray.
* Ordered things (sale sizes, years) use one blue ramp, light to dark.
* "This period vs last year": this period in blue, last year in gray.
* One y-axis per chart, hairline grid, thin bars with rounded ends, 2px lines, hover on every mark.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Reference palette (light), validated: adjacent CVD ΔE ≥ 9.1, normal-vision ΔE ≥ 19.6.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#b9b8b0"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
PRIOR = "#c9c7bf"
RAMP3 = ["#86b6ef", "#2a78d6", "#104281"]              # ordinal, validated
RAMP4 = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]   # ordinal, validated
UP, DOWN, TOTAL = SLOTS[0], SLOTS[7], INK2
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Fixed slot order per dimension. Names not listed (or listed in NEUTRALS) are gray.
DIMENSIONS = {
    "area": ["Sales", "Workshop", "Rentals", "Other"],
    "instrument": ["Violin", "Viola", "Cello", "Bass", "Bow"],
    "ownership": ["Consignment", "DV-owned stock", "Made in-house"],
    "workshop_kind": ["Instrument repairs", "Bow rehairs", "Bow repairs", "Appraisals"],
    "worker": ["Jesse (JF)", "Evan (assumed)", "Eddy (assumed)"],
    "rental_kind": ["Monthly fees", "Annual fees", "Rental insurance", "Late fees", "Short-term & event rentals",
                    "Deposits"],
    "tier": ["Regular", "High-end"],
    "other_kind": ["Strings", "Cases", "Bow hair", "Parts & fittings", "Other products", "Shipping",
                   "Events & concerts"],
    "expense_group": ["Fixed costs", "Variable costs", "Cost of sales"],
    "delinquency": ["Unpaid invoices over 30 days", "Autopay failing 2+ months", "Charges not deposited after 10 days"],
    "consignment": ["Consignment sales", "Paid to consignors", "What DV keeps"],
    "fleet": ["Fleet owned (known purchases)", "On rent"],
    "cumulative": ["Rental revenue", "Spent on rental instruments (known purchases)"],
    "money": ["Revenue", "Expenses", "Net income"],
}
ORDINAL = {"size": ["Under $10k", "$10k–$50k", "$50k and up"]}


def color_map(dim: str, series: list[str]) -> dict[str, str]:
    if dim in ORDINAL:
        return dict(zip(ORDINAL[dim], RAMP3))
    if dim == "years":  # oldest lightest, the current year darkest
        ramp = RAMP4[-len(series):] if len(series) <= 4 else RAMP4
        return dict(zip(sorted(series), ramp))
    fixed = DIMENSIONS.get(dim, [])
    return {s: (SLOTS[fixed.index(s)] if s in fixed else NEUTRAL) for s in series}


# ── Layout ────────────────────────────────────────────────────────────────────────────────────────────
def _layout(fig: go.Figure, money: bool = True, height: int = 360, legend: bool = True, pct: bool = False,
            horizontal: bool = False) -> go.Figure:
    value_axis = dict(gridcolor=GRID, gridwidth=1, zeroline=True, zerolinecolor=AXIS, zerolinewidth=1,
                      tickfont=dict(color=MUTED, size=12), title=None,
                      tickprefix="$" if money else "", tickformat="~s" if money else (".0%" if pct else ",d"))
    cat_axis = dict(showgrid=False, linecolor=AXIS, linewidth=1, ticks="", tickfont=dict(color=INK2, size=12),
                    title=None)
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8 if not legend else 36, b=8),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(family=FONT, color=INK2, size=13),
        showlegend=legend, legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                                       font=dict(color=INK2, size=12), title_text="", traceorder="normal"),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, color=INK, size=13)),
        bargap=0.35, bargroupgap=0.08, barcornerradius=4,
        xaxis=value_axis if horizontal else cat_axis, yaxis=cat_axis if horizontal else value_axis,
    )
    return fig


def _x(rows: pd.DataFrame, grain: str):
    if grain == "month":
        return pd.to_datetime(rows["period"])
    return rows["period_label"].str.replace(" (", "<br>(", regex=False)  # "2026<br>(Jan–Oct)"


def _hover(money: bool, pct: bool = False) -> str:
    v = "$%{y:,.0f}" if money else ("%{y:.0%}" if pct else "%{y:,.0f}")
    return f"<b>{v}</b>  %{{fullData.name}}<extra></extra>"


def _series_order(rows: pd.DataFrame) -> list[str]:
    return rows.drop_duplicates("series").sort_values("sort")["series"].tolist()


# ── Figures ───────────────────────────────────────────────────────────────────────────────────────────
def stacked_bars(rows: pd.DataFrame, dim: str, grain: str = "month", money: bool = True, height: int = 360,
                 average: pd.DataFrame | None = None) -> go.Figure:
    """Stacked columns per period; the in-progress month is drawn lighter. Optional reference line (same axis)."""
    fig = go.Figure()
    order = _series_order(rows)
    colors = color_map(dim, order)
    for s in order:
        r = rows[rows["series"] == s]
        fig.add_bar(x=_x(r, grain), y=r["value"], name=s, marker=dict(
            color=colors[s], opacity=[0.45 if p and grain == "month" else 1 for p in r["partial"]],
            line=dict(color=SURFACE, width=1.5)),
            hovertemplate=_hover(money))
    if average is not None and len(average):
        fig.add_scatter(x=_x(average, grain), y=average["value"], name=average["series"].iloc[0], mode="lines",
                        line=dict(color=INK, width=2), hovertemplate=_hover(money))
    fig.update_layout(barmode="stack", hovermode="x unified")
    if grain == "month":
        fig.update_xaxes(dtick="M3" if rows["period"].nunique() > 14 else "M1", tickformat="%b<br>%Y")
    else:
        fig.update_xaxes(type="category")  # "2026 (Jan–Oct)" is a label, not a number
    return _layout(fig, money, height, legend=len(order) > 1 or average is not None)


def grouped_bars(rows: pd.DataFrame, dim: str, grain: str = "year", money: bool = True,
                 height: int = 340) -> go.Figure:
    fig = go.Figure()
    order = _series_order(rows)
    colors = color_map(dim, order)
    for s in order:
        r = rows[rows["series"] == s]
        fig.add_bar(x=_x(r, grain), y=r["value"], name=s, marker_color=colors[s], hovertemplate=_hover(money))
    fig.update_layout(barmode="group", hovermode="x unified")
    if grain != "month":
        fig.update_xaxes(type="category")
    return _layout(fig, money, height, legend=len(order) > 1)


def lines(rows: pd.DataFrame, dim: str, money: bool = True, height: int = 340, x_labels: bool = False) -> go.Figure:
    fig = go.Figure()
    order = _series_order(rows)
    colors = color_map(dim, order)
    for s in order:
        r = rows[rows["series"] == s].dropna(subset=["value"])
        x = r["period_label"] if x_labels else pd.to_datetime(r["period"])
        fig.add_scatter(x=x, y=r["value"], name=s, mode="lines", line=dict(color=colors[s], width=2, shape="linear"),
                        hovertemplate=_hover(money))
        if len(r):  # end dot with a surface ring
            fig.add_scatter(x=x.iloc[-1:], y=r["value"].iloc[-1:], mode="markers", showlegend=False,
                            hoverinfo="skip", marker=dict(color=colors[s], size=9, line=dict(color=SURFACE, width=2)))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(type="category") if x_labels else fig.update_xaxes(tickformat="%b<br>%Y")
    return _layout(fig, money, height, legend=len(order) > 1)


def this_vs_last_year(rows: pd.DataFrame, now_label: str, prior_label: str, money: bool = True,
                      height: int | None = None) -> go.Figure:
    """Horizontal bars per series: this period (blue) and the same period last year (gray)."""
    order = _series_order(rows)
    r = rows.set_index("series").loc[order[::-1]]  # first series on top
    fig = go.Figure()
    fig.add_bar(y=r.index, x=r["prior"], name=prior_label, orientation="h", marker_color=PRIOR,
                hovertemplate=("<b>$%{x:,.0f}</b>  " if money else "<b>%{x:,.0f}</b>  ") + prior_label + "<extra></extra>")
    fig.add_bar(y=r.index, x=r["value"], name=now_label, orientation="h", marker_color=SLOTS[0],
                hovertemplate=("<b>$%{x:,.0f}</b>  " if money else "<b>%{x:,.0f}</b>  ") + now_label + "<extra></extra>")
    fig.update_layout(barmode="group", hovermode="y unified", legend_traceorder="reversed")
    return _layout(fig, money, height or max(220, 46 * len(order) + 60), horizontal=True)


def ranked_bars(rows: pd.DataFrame, now_label: str, prior_label: str, money: bool = True) -> go.Figure:
    """One bar per category, largest first, with last year's value as a gray tick. For many categories."""
    r = rows.sort_values("value", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=r["series"], x=r["value"], orientation="h", name=now_label, marker_color=SLOTS[0],
                hovertemplate="<b>$%{x:,.0f}</b>  " + now_label + "<extra></extra>")
    fig.add_scatter(y=r["series"], x=r["prior"], mode="markers", name=prior_label,
                    marker=dict(symbol="line-ns", size=16, line=dict(color=INK2, width=2.5)),
                    hovertemplate="<b>$%{x:,.0f}</b>  " + prior_label + "<extra></extra>")
    fig.update_layout(hovermode="y unified")
    return _layout(fig, money, max(240, 30 * len(r) + 70), horizontal=True)


BRIDGE_LABELS = {"Cost of sales": "Cost of<br>sales", "Gross profit": "Gross<br>profit",
                 "Operating expenses": "Operating<br>costs", "Operating profit": "Operating<br>profit",
                 "Discounts, adjustments & other income": "Adjustments &<br>other income",
                 "Non-operating expenses": "Non-operating<br>costs", "Net income": "Net<br>income"}


def waterfall(rows: pd.DataFrame, totals: set[str]) -> go.Figure:
    order = _series_order(rows)
    r = rows.set_index("series").loc[order]
    fig = go.Figure(go.Waterfall(
        # the first bar sets the level; later totals are drawn at their running total
        x=list(r.index), y=r["value"],
        measure=["absolute" if i == 0 else "total" if s in totals else "relative" for i, s in enumerate(r.index)],
        increasing=dict(marker=dict(color=UP)), decreasing=dict(marker=dict(color=DOWN)),
        totals=dict(marker=dict(color=TOTAL)), connector=dict(line=dict(color=AXIS, width=1)),
        texttemplate="%{y:$.3~s}", textposition="outside",
        textfont=dict(color=INK2, size=12), hovertemplate="<b>$%{y:,.0f}</b>  %{x}<extra></extra>",
        cliponaxis=False))
    fig.update_xaxes(tickangle=0, tickvals=list(r.index), ticktext=[BRIDGE_LABELS.get(s, s) for s in r.index])
    _layout(fig, True, 420, legend=False)
    fig.update_layout(margin=dict(t=30))
    return fig


def outlook_band(history: pd.DataFrame, look: pd.DataFrame, height: int = 360) -> go.Figure:
    """Actual months (line) and the next 12 months: typical month (line) inside the usual range (wash)."""
    fig = go.Figure()
    x = pd.to_datetime(look["target_month"])
    fig.add_scatter(x=x, y=look["high"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=x, y=look["low"], mode="lines", line=dict(width=0), fill="tonexty",
                    fillcolor="rgba(42,120,214,0.12)", name="Usual range (8 in 10 months)",
                    hovertemplate="<b>$%{y:,.0f}</b>  low end<extra></extra>")
    fig.add_scatter(x=x, y=look["baseline"], mode="lines", name="Typical month",
                    line=dict(color=SLOTS[0], width=2), hovertemplate="<b>$%{y:,.0f}</b>  typical<extra></extra>")
    if len(history):
        fig.add_scatter(x=pd.to_datetime(history["period"]), y=history["value"], mode="lines", name="Actual",
                        line=dict(color=INK, width=2), hovertemplate="<b>$%{y:,.0f}</b>  actual<extra></extra>")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%b<br>%Y")
    return _layout(fig, True, height)


def config() -> dict:
    return {"displayModeBar": False, "responsive": True}
