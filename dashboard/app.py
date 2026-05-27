"""Denver Violins — Executive Overview.

The landing page rolls every report up to one cross-report view: total revenue
by source and total expenses over the selected range. Section pages (left nav)
drill into each area. Everything reads the pre-aggregated
``clean_datasets_dashboard_aggregates`` sheet.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import (load_expenses_monthly, load_other_income_monthly,
                      load_product_sales_monthly, load_rentals_monthly,
                      load_sales_monthly, load_workshop_monthly)
from lib.filters import date_range_filter
from lib.theme import CATEGORICAL, WINE, apply_theme

st.set_page_config(page_title="Denver Violins", page_icon="🎻", layout="wide")
apply_theme()

st.title("Executive Overview")
st.caption("Total revenue by source and total expenses across the selected "
           "range. Use the left nav to drill into each area.")


def _monthly(df: pd.DataFrame, value: str) -> pd.Series:
    """Sum `value` to month for a source frame; empty frames yield empty."""
    if df is None or not len(df) or value not in df.columns:
        return pd.Series(dtype="float64")
    s = df[df["month"].notna()]
    return s.groupby("month")[value].sum()


# Revenue sources (product sales / other income are empty until materialized
# upstream — they contribute nothing and auto-complete later).
REVENUE_SOURCES = {
    "Rentals": _monthly(load_rentals_monthly(), "revenue"),
    "Instrument Sales": _monthly(load_sales_monthly(), "revenue"),
    "Workshop": _monthly(load_workshop_monthly(), "revenue"),
    "Product Sales": _monthly(load_product_sales_monthly(), "revenue"),
    "Other Income": _monthly(load_other_income_monthly(), "revenue"),
}
expenses = _monthly(load_expenses_monthly(), "amount")

# Union of all months that carry any signal, for the shared date filter.
month_parts = [s.index for s in REVENUE_SOURCES.values() if len(s)]
if len(expenses):
    month_parts.append(expenses.index)
if month_parts:
    union = pd.PeriodIndex(sorted(set().union(*[set(p) for p in month_parts])),
                           freq="M")
    all_months = pd.period_range(union.min(), union.max(), freq="M")
else:
    all_months = pd.PeriodIndex([], freq="M")

st.sidebar.header("Filters")
sel_start, sel_end = date_range_filter(all_months)
span = pd.period_range(sel_start, sel_end, freq="M") if len(all_months) \
    else pd.PeriodIndex([], freq="M")


def _in_range(s: pd.Series) -> pd.Series:
    return s.reindex(span, fill_value=0.0) if len(span) else s.iloc[0:0]


rev_by_source = {name: _in_range(s) for name, s in REVENUE_SOURCES.items()}
exp_in_range = _in_range(expenses)

total_revenue = float(sum(s.sum() for s in rev_by_source.values()))
total_expenses = float(exp_in_range.sum())

# ──────────────────────────────────────────────────────────────────────────
# BANs
# ──────────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("Total revenue (selected range)", f"${total_revenue:,.0f}")
c2.metric("Total expenses (selected range)", f"${total_expenses:,.0f}")
c3.metric("Net (revenue − expenses)", f"${total_revenue - total_expenses:,.0f}")

st.markdown("#### Revenue by source (selected range)")
source_totals = pd.DataFrame(
    {"Source": list(rev_by_source), "Revenue": [s.sum() for s in rev_by_source.values()]}
)
source_totals = source_totals[source_totals["Revenue"] > 0]
if len(source_totals):
    scols = st.columns(len(source_totals))
    for col, (_, row) in zip(scols, source_totals.iterrows()):
        col.metric(row["Source"], f"${row['Revenue']:,.0f}")


# ──────────────────────────────────────────────────────────────────────────
# Timeseries
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


st.markdown("#### Total revenue over time (by source)")
active = [name for name, s in rev_by_source.items() if s.sum() > 0]
if active and len(span):
    long = pd.concat(
        [pd.DataFrame({"month": span.to_timestamp(), "Source": name,
                       "Revenue": rev_by_source[name].to_numpy()})
         for name in active],
        ignore_index=True)
    color_map = {name: CATEGORICAL[i % len(CATEGORICAL)]
                 for i, name in enumerate(active)}
    fig = px.line(long, x="month", y="Revenue", color="Source",
                  color_discrete_map=color_map,
                  labels={"Revenue": "$", "month": ""})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=420, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="exec_revenue_by_source")
else:
    st.caption("No revenue in the selected range.")

st.markdown("#### Total expenses over time")
if len(exp_in_range) and exp_in_range.sum() > 0:
    fig = go.Figure(go.Scatter(
        x=span.to_timestamp(), y=exp_in_range.to_numpy(), mode="lines",
        line=dict(color=WINE, width=3),
        fill="tozeroy", fillcolor="rgba(158,75,59,0.15)", name="Expenses",
        hovertemplate="%{x|%b %Y}<br>Expenses: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=380, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="exec_expenses")
else:
    st.caption("Expense data is not yet materialized upstream; this populates "
               "automatically once available.")
