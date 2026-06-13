"""Other Income page — income that isn't instrument/bow sales, product sales,
workshop services, or rentals. Today that's mostly shipping income; appraisals
and COAs slot in as new income types once they're tagged upstream.

Thin renderer: every measure routes through ``lib.other_income`` over the
pre-aggregated ``other_income_monthly`` tab.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import (SALES_SHEET, global_monthly_span,
                      load_other_income_monthly, source_links)
from lib import other_income as O
from lib.filters import date_range_filter
from lib.theme import CATEGORICAL, SAGE, apply_theme

st.set_page_config(page_title="Other Income — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

st.title("Other Income")
st.caption("Income outside instrument/bow sales, products, workshop, and "
           "rentals. Cash basis. Daily refresh from cleaned Google Sheets.")
st.info("Today this is mainly shipping income; appraisals and COAs will appear "
        "here as distinct income types once they're tagged upstream.",
        icon="ℹ️")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters (date range persists across pages)
# ──────────────────────────────────────────────────────────────────────────
income_all = load_other_income_monthly()
all_months = global_monthly_span()
start, end = date_range_filter(all_months)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= start) & (df["month"] <= end)]


income = in_range(income_all)
span = O.monthly_span(income) if len(income) else (
    pd.period_range(start, end, freq="M") if len(all_months) else
    pd.PeriodIndex([], freq="M"))

if income_all.empty:
    st.info("No data yet — this report populates once the upstream aggregate "
            "is built.", icon="ℹ️")

# ──────────────────────────────────────────────────────────────────────────
# KPIs (reflect the selected date range)
# ──────────────────────────────────────────────────────────────────────────
kpi = O.kpi_snapshot(income, span)
st.subheader(f"Selected range — through {kpi['as_of']}")

# Total + one card per income type (capped so the row stays readable).
cards = [("Total Other Income", kpi["total_revenue"])]
cards += [(t, v) for t, v in kpi["by_type"][:4]]
cols = st.columns(len(cards))
for col, (label, value) in zip(cols, cards):
    col.metric(label, f"${value:,.0f}")
st.caption("Totals reflect the selected date range. Latest month may be "
           "partial — figures update daily.")


# ──────────────────────────────────────────────────────────────────────────
# Chart helper
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


# ──────────────────────────────────────────────────────────────────────────
# Charts + table
# ──────────────────────────────────────────────────────────────────────────
st.markdown("#### Monthly other income")
source_links(("", SALES_SHEET, "shipping_income_df"))
rev_total = O.revenue_by_month(income, span)
fig = go.Figure(go.Bar(x=rev_total["month"], y=rev_total["revenue"],
                       name="Other income", marker_color=SAGE,
                       hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"))
fig.update_layout(height=360, yaxis_title="$", yaxis_tickprefix="$",
                  yaxis_tickformat=",.0f", showlegend=False)
st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

st.markdown("#### Other income by type")
source_links(("", SALES_SHEET, "shipping_income_df"))
types = O.income_types(income)
cmap = {t: CATEGORICAL[i % len(CATEGORICAL)] for i, t in enumerate(types)}
rev_t = O.revenue_by_month(income, span, by="income_type")
fig = px.line(rev_t, x="month", y="revenue", color="group",
              color_discrete_map=cmap,
              labels={"revenue": "$", "group": "Income type"})
fig.update_traces(line=dict(width=2.5))
fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

st.markdown("#### Breakdown by income type")
source_links(("", SALES_SHEET, "shipping_income_df"))
breakdown = O.type_breakdown(income)
if not len(breakdown):
    st.info("No other-income rows in the current filter set.", icon="ℹ️")
else:
    st.dataframe(
        breakdown,
        hide_index=True,
        use_container_width=True,
        column_config={
            "income_type": st.column_config.TextColumn("Income type"),
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
            "transactions": st.column_config.NumberColumn(
                "Transactions", format="%d"),
            "revenue_share": st.column_config.ProgressColumn(
                "Share of revenue", min_value=0.0,
                max_value=float(breakdown["revenue_share"].max() or 1.0),
                format="%.1f%%"),
        },
    )
