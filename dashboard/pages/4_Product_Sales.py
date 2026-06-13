"""Product Sales page — the accessory line (rosin, cases, strings, accessory
bows, …): sales revenue/units plus the standing product inventory.

Thin renderer: every measure routes through ``lib.products`` over the
pre-aggregated ``product_sales_monthly`` and ``product_inventory_monthly`` tabs.
Instrument and instrument-grade bow sales live on the Sales page; this is the
``Sales of Product Income`` accessory line only.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import (PURCHASES_SHEET, SALES_SHEET, global_monthly_span,
                      load_product_inventory, load_product_sales_monthly,
                      source_links)
from lib import products as P
from lib.filters import date_range_filter
from lib.theme import BROWN, CATEGORICAL, SAGE, SLATE, apply_theme

st.set_page_config(page_title="Product Sales — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

st.title("Product Sales")
st.caption("Accessory products — rosin, cases, strings, accessory bows, and the "
           "rest of the retail line. Sales revenue and units, plus standing "
           "inventory. Cash basis. Daily refresh from cleaned Google Sheets.")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters (date range persists across pages)
# ──────────────────────────────────────────────────────────────────────────
sales_all = load_product_sales_monthly()
inv_all = load_product_inventory()

all_months = global_monthly_span()
start, end = date_range_filter(all_months)

all_categories = sorted(
    set(sales_all["product_category"].dropna().astype(str))
    | set(inv_all["product_category"].dropna().astype(str))
)
sel_categories = st.sidebar.multiselect(
    "Product category",
    options=all_categories,
    default=all_categories,
    help="Optional — deselect to focus on specific product categories.",
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= start) & (df["month"] <= end)]


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    if not all_categories:          # nothing to filter on yet (empty data)
        return df
    if not sel_categories:
        return df.iloc[0:0]
    return df[df["product_category"].isin(sel_categories)]


sales = by_category(in_range(sales_all))
inv = by_category(in_range(inv_all))
span = P.monthly_span(sales, inv) if (len(sales) or len(inv)) else (
    pd.period_range(start, end, freq="M") if len(all_months) else
    pd.PeriodIndex([], freq="M"))

if sales_all.empty and inv_all.empty:
    st.info("No data yet — this report populates once the upstream aggregate "
            "is built.", icon="ℹ️")


# ──────────────────────────────────────────────────────────────────────────
# Chart helper
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


_CAT_CMAP = {c: CATEGORICAL[i % len(CATEGORICAL)]
             for i, c in enumerate(all_categories)}

# ──────────────────────────────────────────────────────────────────────────
# Tabs: Revenue, Inventory
# ──────────────────────────────────────────────────────────────────────────
tab_rev, tab_inv = st.tabs(["Revenue & Units", "Inventory"])

# ── Revenue & Units ─────────────────────────────────────────────────────────
with tab_rev:
    kpi = P.sales_kpis(sales, span)
    st.subheader(f"Selected range — through {kpi['as_of']}")
    c1, c2 = st.columns(2)
    lr, lrd = kpi["latest_revenue"]
    lu, lud = kpi["latest_units"]
    c1.metric("Total Product Sales Revenue", f"${kpi['total_revenue']:,.0f}",
              help="Sum across the selected date range.")
    c2.metric("Total Products Sold", f"{kpi['total_units']:,.0f}",
              help="Units sold across the selected date range.")
    st.caption("Totals reflect the selected date range. Latest month may be "
               "partial — figures update daily.")

    st.markdown("#### Monthly revenue and products sold")
    source_links(("", SALES_SHEET, "product_sales_df"))
    rev = P.revenue_by_month(sales, span)
    units = P.units_by_month(sales, span)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=rev["month"], y=rev["revenue"], name="Revenue",
                         marker_color=SAGE,
                         hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}"
                                       "<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=units["month"], y=units["units"],
                             name="Products sold", mode="lines+markers",
                             line=dict(color=BROWN, width=2.5),
                             hovertemplate="%{x|%b %Y}<br>Units: %{y:,.0f}"
                                           "<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text="$", tickprefix="$", tickformat=",.0f",
                     secondary_y=False)
    fig.update_yaxes(title_text="Units", secondary_y=True)
    fig.update_layout(height=400)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Revenue by product category")
    source_links(("", SALES_SHEET, "product_sales_df"))
    rev_c = P.revenue_by_month(sales, span, by="product_category")
    fig = px.line(rev_c, x="month", y="revenue", color="group",
                  color_discrete_map=_CAT_CMAP,
                  labels={"revenue": "$", "group": "Category"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Breakdown by category and subcategory")
    source_links(("", SALES_SHEET, "product_sales_df"))
    breakdown = P.category_breakdown(sales)
    if not len(breakdown):
        st.info("No product sales in the current filter set.", icon="ℹ️")
    else:
        st.dataframe(
            breakdown,
            hide_index=True,
            use_container_width=True,
            column_config={
                "product_category": st.column_config.TextColumn("Category"),
                "product_subcategory": st.column_config.TextColumn(
                    "Subcategory"),
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="$%.0f"),
                "units": st.column_config.NumberColumn("Units", format="%d"),
                "transactions": st.column_config.NumberColumn(
                    "Transactions", format="%d"),
                "revenue_share": st.column_config.ProgressColumn(
                    "Share of revenue", min_value=0.0,
                    max_value=float(breakdown["revenue_share"].max() or 1.0),
                    format="%.1f%%"),
            },
        )

# ── Inventory ────────────────────────────────────────────────────────────────
with tab_inv:
    snap = P.inventory_snapshot(inv, span)
    st.subheader(f"As of {snap['as_of']}")
    c1, c2 = st.columns(2)
    u, ud = snap["units"]
    cost, cost_d = snap["cost"]
    c1.metric("Total Product Inventory (units)", f"{u:,.0f}",
              f"{ud:+,.0f} vs prior mo",
              help="Standing stock as of the latest month in range.")
    c2.metric("Inventory Cost", f"${cost:,.0f}", f"{cost_d:+,.0f} vs prior mo",
              help="Cumulative cost of stock on hand, latest month in range.")
    st.caption("Inventory is a standing level (not a flow): these are the "
               "as-of-today totals for the latest month in the selected range.")

    st.markdown("#### Inventory units and cost over time")
    source_links(("", PURCHASES_SHEET, "accessories_products_df"))
    by_m = P.inventory_by_month(inv, span)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=by_m["month"], y=by_m["units"], name="Units",
                             mode="lines", line=dict(color=SLATE, width=3),
                             hovertemplate="%{x|%b %Y}<br>Units: %{y:,.0f}"
                                           "<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=by_m["month"], y=by_m["cost"], name="Cost",
                             mode="lines", line=dict(color=BROWN, width=3),
                             hovertemplate="%{x|%b %Y}<br>Cost: $%{y:,.0f}"
                                           "<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text="Units", secondary_y=False)
    fig.update_yaxes(title_text="$", tickprefix="$", tickformat=",.0f",
                     secondary_y=True)
    fig.update_layout(height=400)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Stock on hand by category (as of latest month)")
    source_links(("", PURCHASES_SHEET, "accessories_products_df"))
    inv_bd = P.inventory_breakdown(inv, span)
    if not len(inv_bd):
        st.info("No product inventory in the current filter set.", icon="ℹ️")
    else:
        st.dataframe(
            inv_bd,
            hide_index=True,
            use_container_width=True,
            column_config={
                "product_category": st.column_config.TextColumn("Category"),
                "units": st.column_config.NumberColumn("Units", format="%d"),
                "cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
            },
        )
