"""Workshop page — services revenue and activity, grouped by month / service
category / instrument-vs-bow / employee.

The page never computes metrics inline; everything routes through
``lib.workshop`` so definitions stay centralized. The employee filter derives
its options from the data's distinct employee values.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import load_workshop_monthly
from lib.filters import date_range_filter
from lib import workshop as W
from lib.theme import (BROWN, CATEGORICAL, GOLD, SAGE, SLATE, apply_theme)

st.set_page_config(page_title="Workshop — Denver Violins",
                   page_icon="🔧", layout="wide")
apply_theme()

PRODUCT_SERVICE_COLORS = {
    "Instrument services": BROWN,
    "Bow services": GOLD,
}
# Three benches; the data may carry only a subset until upstream re-materializes.
EMPLOYEE_PALETTE = {
    "JF": GOLD,
    "Evan Orman": SLATE,
    "Eddie Miller": BROWN,
}

# ──────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────
st.title("Workshop")
st.caption("Services revenue and activity — instrument repair, bow rehairs, "
           "appraisals, and other bench work. Cash basis.")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
services_all = load_workshop_monthly()
all_months = W.monthly_span(services_all)
all_categories = sorted(services_all["service_name"].dropna().unique().tolist())
all_employees = sorted(services_all["employee_label"].dropna().unique().tolist())

st.sidebar.header("Filters")
sel_start, sel_end = date_range_filter(all_months)
sel_product = st.sidebar.radio(
    "Service type",
    options=["Both", "Instrument services only", "Bow services only"],
    index=0,
)
sel_categories = st.sidebar.multiselect(
    "Service category",
    options=all_categories,
    default=all_categories,
)
sel_employees = st.sidebar.multiselect(
    "Employee",
    options=all_employees,
    default=all_employees,
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= sel_start) & (df["month"] <= sel_end)]


def by_product(df: pd.DataFrame) -> pd.DataFrame:
    if sel_product == "Instrument services only":
        return df[~df["bow_flag"]]
    if sel_product == "Bow services only":
        return df[df["bow_flag"]]
    return df


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["service_name"].isin(sel_categories)] if sel_categories else df.iloc[0:0]


def by_employee(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["employee_label"].isin(sel_employees)] if sel_employees else df.iloc[0:0]


services = by_employee(by_category(by_product(in_range(services_all))))
span = W.monthly_span(services) if len(services) else all_months

# ──────────────────────────────────────────────────────────────────────────
# BANs — selected range
# ──────────────────────────────────────────────────────────────────────────
kpi = W.kpi_snapshot(services, span)

c1, c2 = st.columns(2)
c1.metric("Total services revenue (selected range)",
          f"${kpi['all_time_revenue']:,.0f}")
c2.metric("Total jobs (selected range)",
          f"{kpi['all_time_transactions']:,.0f}")

st.caption("Services are billed per-job, so 'Jobs' counts line-item rows. The "
           "latest month may be partial.")


# ──────────────────────────────────────────────────────────────────────────
# Chart helpers
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


# ──────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────
tab_overview, tab_cat, tab_split, tab_emp = st.tabs(
    ["Overview", "By Service Category",
     "Instrument vs Bow", "By Employee"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    st.markdown("#### Monthly services revenue")
    rev = W.revenue_by_month(services, span)
    fig = go.Figure(go.Scatter(
        x=rev["month"], y=rev["revenue"], mode="lines",
        line=dict(color=SAGE, width=3),
        fill="tozeroy", fillcolor="rgba(122,158,126,0.15)", name="Revenue",
        hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=400, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_overview_revenue")

    st.markdown("#### Jobs per month")
    jobs = W.transactions_by_month(services, span)
    fig = go.Figure(go.Scatter(
        x=jobs["month"], y=jobs["transactions"], mode="lines",
        line=dict(color=BROWN, width=2.5), name="Jobs",
        hovertemplate="%{x|%b %Y}<br>Jobs: %{y:,.0f}<extra></extra>"))
    fig.update_layout(height=320, yaxis_title="Jobs")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_overview_jobs")

# ── By Service Category ───────────────────────────────────────────────────
with tab_cat:
    st.markdown("#### Top categories by revenue")
    top_n = 6
    top_cats = W.top_n_categories(services, n=top_n)
    if not top_cats:
        st.info("No service rows in the current filter set.", icon="ℹ️")
    else:
        collapsed = W.with_collapsed_category(services, keep=top_cats)
        rev_c = W.revenue_by_month(collapsed, span, by="category_collapsed")
        order = top_cats + [W.OTHER_LABEL]
        color_map = {cat: CATEGORICAL[i % len(CATEGORICAL)]
                     for i, cat in enumerate(order)}
        fig = px.line(rev_c, x="month", y="revenue", color="group",
                      category_orders={"group": order},
                      color_discrete_map=color_map,
                      labels={"revenue": "$", "group": "Service category"})
        fig.update_traces(line=dict(width=2.5))
        fig.update_layout(height=420, yaxis_tickprefix="$",
                          yaxis_tickformat=",.0f")
        st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                        key="ws_top_categories")
        st.caption(f"Top {top_n} categories shown explicitly; everything else "
                   "folded into 'Other'. Full breakdown below.")

    st.markdown("#### Full breakdown")
    breakdown = W.category_breakdown(services)
    if not len(breakdown):
        st.info("No rows to break down.", icon="ℹ️")
    else:
        st.dataframe(
            breakdown,
            hide_index=True,
            use_container_width=True,
            column_config={
                "service_name": st.column_config.TextColumn("Category"),
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="$%.0f"),
                "transactions": st.column_config.NumberColumn(
                    "Jobs", format="%d"),
                "revenue_share": st.column_config.ProgressColumn(
                    "Share of revenue",
                    min_value=0.0,
                    max_value=100.0,
                    format="%.1f%%"),
            },
        )

# ── Instrument vs Bow ─────────────────────────────────────────────────────
with tab_split:
    order = ["Instrument services", "Bow services"]

    st.markdown("#### Revenue: instrument vs bow services")
    rev_pt = W.revenue_by_month(services, span, by="bow_flag")
    fig = px.line(rev_pt, x="month", y="revenue", color="group",
                  color_discrete_map=PRODUCT_SERVICE_COLORS,
                  category_orders={"group": order},
                  labels={"revenue": "$", "group": "Service type"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_split_revenue")

    st.markdown("#### Jobs: instrument vs bow services")
    jobs_pt = W.transactions_by_month(services, span, by="bow_flag")
    fig = px.line(jobs_pt, x="month", y="transactions", color="group",
                  color_discrete_map=PRODUCT_SERVICE_COLORS,
                  category_orders={"group": order},
                  labels={"transactions": "Jobs", "group": "Service type"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_split_jobs")

    totals = (services.groupby("bow_flag")
                      .agg(revenue=("revenue", "sum"),
                           jobs=("jobs", "sum"))
                      .reset_index())
    if len(totals):
        st.markdown("#### Totals (selected range)")
        scols = st.columns(len(totals))
        for col, (_, row) in zip(scols, totals.iterrows()):
            label = "Bow services" if row["bow_flag"] else "Instrument services"
            col.metric(f"{label} — revenue", f"${row['revenue']:,.0f}",
                       help=f"{int(row['jobs']):,} jobs.")

# ── By Employee ───────────────────────────────────────────────────────────
with tab_emp:
    present = [e for e in EMPLOYEE_PALETTE if e in set(services["employee_label"])]
    extra = sorted(set(services["employee_label"]) - set(EMPLOYEE_PALETTE))
    order = present + extra

    st.markdown("#### Revenue by employee over time")
    rev_e = W.revenue_by_month(services, span, by="employee_label")
    fig = px.line(rev_e, x="month", y="revenue", color="group",
                  color_discrete_map=EMPLOYEE_PALETTE,
                  category_orders={"group": order},
                  labels={"revenue": "$", "group": "Employee"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_employee_revenue")

    st.markdown("#### Jobs by employee over time")
    jobs_e = W.transactions_by_month(services, span, by="employee_label")
    fig = px.line(jobs_e, x="month", y="transactions", color="group",
                  color_discrete_map=EMPLOYEE_PALETTE,
                  category_orders={"group": order},
                  labels={"transactions": "Jobs", "group": "Employee"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="ws_employee_jobs")

    totals = (services.groupby("employee_label")
                      .agg(revenue=("revenue", "sum"),
                           jobs=("jobs", "sum"))
                      .reset_index()
                      .sort_values("revenue", ascending=False))
    if len(totals):
        st.markdown("#### Totals (selected range)")
        scols = st.columns(len(totals))
        for col, (_, row) in zip(scols, totals.iterrows()):
            col.metric(f"{row['employee_label']} — revenue",
                       f"${row['revenue']:,.0f}",
                       help=f"{int(row['jobs']):,} jobs.")
