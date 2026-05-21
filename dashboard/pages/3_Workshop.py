"""Workshop page — Mack's headline metrics for services revenue, grouped by
month / service category / instrument-vs-bow / employee.

The page never computes metrics inline; everything routes through
``lib.workshop`` so definitions stay centralized and swappable.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import load_services_sales
from lib import workshop as W
from lib.theme import (BROWN, GOLD, PRODUCT_TYPE_COLORS, SAGE, SLATE,
                       WARM_GRAY, WINE, apply_theme)

st.set_page_config(page_title="Workshop — Denver Violins",
                   page_icon="🔧", layout="wide")
apply_theme()

# Bow services share Bow color with Sales; instrument services share Brown.
PRODUCT_SERVICE_COLORS = {
    "Instrument services": BROWN,
    "Bow services": GOLD,
}
EMPLOYEE_PALETTE = {
    "JF": GOLD,
    "Evan Orman": SLATE,
}

# ──────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────
st.title("Workshop")
st.caption("Services revenue and activity — instrument repair, bow rehairs, "
           "appraisals, and the rest of the bench work. Cash basis. Daily "
           "refresh from cleaned Google Sheets.")

with st.expander("Data notes — read once", expanded=False):
    st.markdown(
        """
        **Cash basis only.** Same constraint as the Sales page — the accrual
        export isn't staged yet.

        **What's counted.** Every row in
        `clean_datasets_sales_by_product_cash / services_sales_df` — upstream
        filter is `distribution_account in ('Services', 'Bow Services')`.
        Rental-fee leakage that got misfiled under Services is routed back to
        rentals during staging (KB `11_data_classification`), so this view is
        services-only.

        **Service category** comes from `utils.categorize_service` — 22
        buckets (Bow Rehair, Bridge Work, Sound Post Work, …). The headline
        chart keeps the top categories by revenue and folds the rest into
        "Other"; the **Full breakdown** table below the chart shows every
        category.

        **Instrument vs Bow services.** Driven by the staging `bow_flag`,
        which catches bow rehairs and other bow work even when they're
        booked to the `Services` account — so it's a cleaner split than
        `distribution_account`.

        **Per-instrument (violin / viola / cello) view is intentionally not
        shown.** ~62 % of service rows have `instrument == 'unknown'`
        because the memo doesn't name the instrument family. A per-instrument
        chart would be dominated by an "Unknown" bar that wouldn't help
        anyone. Revisit once `extract_instrument_metadata` is extended to
        service memos.

        **Employee = `JF` or `EO` only — and `EO` means Evan Orman.**
        `utils.find_employee` tags a row `JF` when the memo contains "jf"
        and defaults *everything else* to `EO` (**Evan Orman**, co-owner /
        master bow maker). There's no code for **Eddie Miller** (co-owner &
        Mack's husband / master violin maker) yet — his would be `EM` — so
        any of Eddie's bench work that isn't tagged `JF` is currently
        **misattributed to Evan Orman**. Until an `EM` rule is added to the
        classifier, read the **Evan Orman** series as "Evan + any of Eddie's
        untagged work." Tracked in `09_known_issues §find_employee`.
        """
    )

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
services_all = load_services_sales()
all_months = W.monthly_span(services_all)
month_strings = [str(m) for m in all_months]
all_categories = sorted(services_all["service_name"].dropna().unique().tolist())

st.sidebar.header("Filters")
sel_start, sel_end = st.sidebar.select_slider(
    "Month range",
    options=month_strings,
    value=(month_strings[0], month_strings[-1]),
)
sel_product = st.sidebar.radio(
    "Service type",
    options=["Both", "Instrument services only", "Bow services only"],
    index=0,
    help="`bow_flag` from staging — covers bow rehairs even when booked to "
         "the Services account.",
)
sel_categories = st.sidebar.multiselect(
    "Service category",
    options=all_categories,
    default=all_categories,
    help="22 categories from utils.categorize_service. Deselect to focus.",
)
sel_employee = st.sidebar.radio(
    "Employee",
    options=["Both", "JF only", "Evan Orman (EO) only"],
    index=0,
    help="EO = Evan Orman. Eddie Miller's untagged work is currently "
         "misattributed here (no EM code yet) — see Data notes.",
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= pd.Period(sel_start))
              & (df["month"] <= pd.Period(sel_end))]


def by_product(df: pd.DataFrame) -> pd.DataFrame:
    if sel_product == "Instrument services only":
        return df[~df["bow_flag"]]
    if sel_product == "Bow services only":
        return df[df["bow_flag"]]
    return df


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["service_name"].isin(sel_categories)] if sel_categories else df.iloc[0:0]


def by_employee(df: pd.DataFrame) -> pd.DataFrame:
    if sel_employee == "JF only":
        return df[df["employee_name"] == "JF"]
    if sel_employee == "Evan Orman (EO) only":
        return df[df["employee_name"] == "EO"]
    return df


services = by_employee(by_category(by_product(in_range(services_all))))
span = W.monthly_span(services) if len(services) else all_months

# ──────────────────────────────────────────────────────────────────────────
# KPI row
# ──────────────────────────────────────────────────────────────────────────
kpi = W.kpi_snapshot(services, span)
st.subheader(f"As of {kpi['as_of']}")

c1, c2, c3, c4 = st.columns(4)
rev, rev_d = kpi["revenue"]
txn, txn_d = kpi["transactions"]
c1.metric("Revenue (this month)", f"${rev:,.0f}",
          f"{rev_d:+,.0f} vs prior mo")
c2.metric("Jobs (this month)", f"{txn:,.0f}",
          f"{txn_d:+,.0f} vs prior mo")
c3.metric("All-time revenue", f"${kpi['all_time_revenue']:,.0f}",
          help="Sum across the filtered month range.")
c4.metric("All-time jobs", f"{kpi['all_time_transactions']:,.0f}",
          help="Sum of service line-item rows across the filtered range.")

st.caption("Latest month may be partial — figures update daily. Services are "
           "billed per-job, so 'Jobs' counts line-item rows, not "
           "instruments-shipped-back.")


# ──────────────────────────────────────────────────────────────────────────
# Chart helpers
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


def _revenue_jobs_combo(df_rev: pd.DataFrame, df_jobs: pd.DataFrame,
                         rev_color: str = SAGE,
                         jobs_color: str = BROWN) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_rev["month"], y=df_rev["revenue"], name="Revenue",
                         marker_color=rev_color,
                         hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}"
                                       "<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=df_jobs["month"], y=df_jobs["transactions"],
                             name="Jobs", mode="lines+markers",
                             line=dict(color=jobs_color, width=2.5),
                             hovertemplate="%{x|%b %Y}<br>Jobs: %{y:,.0f}"
                                           "<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text="$", tickprefix="$", tickformat=",.0f",
                     secondary_y=False)
    fig.update_yaxes(title_text="Jobs", secondary_y=True)
    fig.update_layout(height=400)
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
    st.markdown("#### Monthly revenue and job count")
    rev = W.revenue_by_month(services, span)
    jobs = W.transactions_by_month(services, span)
    st.plotly_chart(_shared_xaxis(_revenue_jobs_combo(rev, jobs)),
                    use_container_width=True)
    st.caption("Bars = revenue (cash received this month). Line = jobs "
               "(service line-items recorded this month). Revenue and jobs "
               "track closely for the workshop since most services are paid "
               "on completion.")

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
        fig = px.bar(rev_c, x="month", y="revenue", color="group",
                     category_orders={"group": order},
                     labels={"revenue": "$", "group": "Service category"})
        fig.update_layout(height=420, yaxis_tickprefix="$",
                          yaxis_tickformat=",.0f", barmode="stack")
        st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
        st.caption(f"Top {top_n} categories shown explicitly; everything else "
                   "folded into 'Other'. Full breakdown below.")

    st.markdown("#### Full breakdown (all 22 categories)")
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
                    max_value=float(breakdown["revenue_share"].max() or 1.0),
                    format="%.1f%%"),
            },
        )

# ── Instrument vs Bow ─────────────────────────────────────────────────────
with tab_split:
    st.markdown("#### Revenue: instrument vs bow services")
    rev_pt = W.revenue_by_month(services, span, by="bow_flag")
    fig = px.bar(rev_pt, x="month", y="revenue", color="group",
                 color_discrete_map=PRODUCT_SERVICE_COLORS,
                 category_orders={"group": ["Instrument services",
                                            "Bow services"]},
                 labels={"revenue": "$", "group": "Service type"})
    fig.update_layout(height=380, yaxis_tickprefix="$",
                      yaxis_tickformat=",.0f", barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Jobs: instrument vs bow services")
    jobs_pt = W.transactions_by_month(services, span, by="bow_flag")
    fig = px.bar(jobs_pt, x="month", y="transactions", color="group",
                 color_discrete_map=PRODUCT_SERVICE_COLORS,
                 category_orders={"group": ["Instrument services",
                                            "Bow services"]},
                 labels={"transactions": "Jobs", "group": "Service type"})
    fig.update_layout(height=380, barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    # Side stat: all-time totals per service type
    totals = (services.groupby("bow_flag")
                      .agg(revenue=("amount", "sum"),
                           jobs=("amount", "size"))
                      .reset_index())
    if len(totals):
        st.markdown("#### All-time totals")
        cols = st.columns(len(totals))
        for col, (_, row) in zip(cols, totals.iterrows()):
            label = "Bow services" if row["bow_flag"] else "Instrument services"
            col.metric(f"{label} — revenue", f"${row['revenue']:,.0f}",
                       help=f"{int(row['jobs']):,} jobs.")

# ── By Employee ───────────────────────────────────────────────────────────
with tab_emp:
    st.warning(
        "**`EO` = Evan Orman — but Eddie Miller's work is currently "
        "misattributed to it.** `utils.find_employee` only emits `JF` or "
        "`EO`; anything not tagged `JF` defaults to `EO` (**Evan Orman**, "
        "co-owner / master bow maker). There's no `EM` code for **Eddie "
        "Miller** (co-owner & Mack's husband / master violin maker) yet, so "
        "any of Eddie's untagged bench work lands in the Evan Orman bar. Fix "
        "is an `EM` rule in the classifier (`09_known_issues §find_employee`); "
        "Eddie splits into his own series once that lands.",
        icon="⚠️",
    )

    st.markdown("#### Revenue by employee")
    rev_e = W.revenue_by_month(services, span, by="employee_label")
    fig = px.bar(rev_e, x="month", y="revenue", color="group",
                 color_discrete_map=EMPLOYEE_PALETTE,
                 category_orders={"group": ["JF", "Evan Orman"]},
                 labels={"revenue": "$", "group": "Employee"})
    fig.update_layout(height=380, yaxis_tickprefix="$",
                      yaxis_tickformat=",.0f", barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Jobs by employee")
    jobs_e = W.transactions_by_month(services, span, by="employee_label")
    fig = px.bar(jobs_e, x="month", y="transactions", color="group",
                 color_discrete_map=EMPLOYEE_PALETTE,
                 category_orders={"group": ["JF", "Evan Orman"]},
                 labels={"transactions": "Jobs", "group": "Employee"})
    fig.update_layout(height=380, barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    # Side stat: all-time totals per employee
    totals = (services.groupby("employee_label")
                      .agg(revenue=("amount", "sum"),
                           jobs=("amount", "size"))
                      .reset_index()
                      .sort_values("revenue", ascending=False))
    if len(totals):
        st.markdown("#### All-time totals")
        cols = st.columns(len(totals))
        for col, (_, row) in zip(cols, totals.iterrows()):
            col.metric(f"{row['employee_label']} — revenue",
                       f"${row['revenue']:,.0f}",
                       help=f"{int(row['jobs']):,} jobs.")
