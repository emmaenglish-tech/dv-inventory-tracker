"""Instrument Sales page — revenue and units for instrument and bow sales,
grouped by month / instrument / acquisition source.

The page never computes metrics inline; everything routes through lib.sales so
definitions stay centralized. A bow counts as one of the instrument groups
(lib.instruments), so there is no separate bow view.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import (SALES_SHEET, global_monthly_span, load_sales_monthly,
                      source_links)
from lib.filters import date_range_filter
from lib.instruments import add_instrument_group, ordered_present
from lib import sales as S
from lib.theme import GOLD, INSTRUMENT_GROUP_COLORS, SAGE, SLATE, apply_theme

st.set_page_config(page_title="Instrument Sales — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

# Acquisition source colors (theme OWNERSHIP_COLORS keys predate the "DV-Owned"
# label, so the page maps its own consistent pair).
ACQUISITION_COLORS = {"Consignment": GOLD, "DV-Owned": SLATE}

st.title("Instrument Sales")
st.caption("Revenue and units for instrument and bow sales, with the "
           "consignment vs DV-owned acquisition split. Cash basis.")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
sales_all = add_instrument_group(load_sales_monthly())
all_months = global_monthly_span()

st.sidebar.header("Filters")
sel_start, sel_end = date_range_filter(all_months)

group_options = ordered_present(sales_all["instrument_group"].unique())
sel_groups = st.sidebar.multiselect(
    "Instrument type",
    options=group_options,
    default=group_options,
    help="A bow is one of the instrument groups.",
)
sel_acq = st.sidebar.radio(
    "Acquisition source",
    options=["Both", "DV-Owned only", "Consignment only"],
    index=0,
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= sel_start) & (df["month"] <= sel_end)]


def by_group(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["instrument_group"].isin(sel_groups)] if sel_groups else df.iloc[0:0]


def by_acquisition(df: pd.DataFrame) -> pd.DataFrame:
    if sel_acq == "DV-Owned only":
        return df[df["ownership"] == "dv_owned"]
    if sel_acq == "Consignment only":
        return df[df["ownership"] == "consignment"]
    return df


sales = by_acquisition(by_group(in_range(sales_all)))
span = S.monthly_span(sales) if len(sales) else all_months

# ──────────────────────────────────────────────────────────────────────────
# BANs — selected range
# ──────────────────────────────────────────────────────────────────────────
kpi = S.kpi_snapshot(sales, span)

# Outstanding balances are only shown if the aggregate carries them.
has_outstanding = "outstanding_balance" in sales.columns
cols = st.columns(3 if has_outstanding else 2)
cols[0].metric("Total instrument sales revenue (selected range)",
               f"${kpi['all_time_revenue']:,.0f}")
cols[1].metric("Total instruments sold (selected range)",
               f"{kpi['all_time_units']:,.0f}")
if has_outstanding:
    outstanding = float(sales["outstanding_balance"].sum())
    cols[2].metric("Total outstanding balances (selected range)",
                   f"${outstanding:,.0f}")

st.caption("Units count each sale once on its final-payment month; the latest "
           "month may be partial.")


# ──────────────────────────────────────────────────────────────────────────
# Chart helpers
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


def _line_by_group(df: pd.DataFrame, value: str, order: list[str],
                   color_map: dict, value_label: str, group_label: str,
                   dollars: bool = False) -> go.Figure:
    fig = px.line(df, x="month", y=value, color="group",
                  category_orders={"group": order},
                  color_discrete_map=color_map,
                  labels={value: value_label, "group": group_label})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    if dollars:
        fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    return fig


# ──────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────
tab_overview, tab_instr, tab_acq = st.tabs(
    ["Overview", "By Instrument", "Acquisition Source"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    st.markdown("#### Monthly sales revenue")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    rev = S.revenue_by_month(sales, span)
    fig = go.Figure(go.Scatter(
        x=rev["month"], y=rev["revenue"], mode="lines",
        line=dict(color=SAGE, width=3),
        fill="tozeroy", fillcolor="rgba(122,158,126,0.15)", name="Revenue",
        hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=400, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="sales_overview_revenue")

    st.markdown("#### Units sold per month")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    units = S.units_sold_by_month(sales, span)
    fig = go.Figure(go.Scatter(
        x=units["month"], y=units["units"], mode="lines",
        line=dict(color=GOLD, width=2.5), name="Units",
        hovertemplate="%{x|%b %Y}<br>Units: %{y:,.0f}<extra></extra>"))
    fig.update_layout(height=320, yaxis_title="Units")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="sales_overview_units")
    st.caption("Revenue trickles in over installment months; units register "
               "only on the final payment, so the two series can diverge.")

# ── By Instrument ─────────────────────────────────────────────────────────
with tab_instr:
    order = ordered_present(sales["instrument_group"].unique())

    st.markdown("#### Revenue by instrument over time")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    rev_i = S.revenue_by_month(sales, span, by="instrument_group")
    st.plotly_chart(
        _shared_xaxis(_line_by_group(rev_i, "revenue", order,
                                     INSTRUMENT_GROUP_COLORS, "$", "Instrument",
                                     dollars=True)),
        use_container_width=True, key="sales_instr_revenue")

    st.markdown("#### Units sold by instrument over time")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    units_i = S.units_sold_by_month(sales, span, by="instrument_group")
    st.plotly_chart(
        _shared_xaxis(_line_by_group(units_i, "units", order,
                                     INSTRUMENT_GROUP_COLORS, "Units",
                                     "Instrument")),
        use_container_width=True, key="sales_instr_units")

# ── Acquisition Source ────────────────────────────────────────────────────
with tab_acq:
    st.caption("Acquisition source is how Denver Violins acquired the "
               "instrument: on consignment, or DV-owned. A finer Wholesale vs "
               "Auction split for DV-owned sales is pending an upstream data "
               "tag.")
    order = ["Consignment", "DV-Owned"]

    st.markdown("#### Revenue by acquisition source over time")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    rev_o = S.revenue_by_month(sales, span, by="ownership")
    st.plotly_chart(
        _shared_xaxis(_line_by_group(rev_o, "revenue", order, ACQUISITION_COLORS,
                                     "$", "Acquisition source", dollars=True)),
        use_container_width=True, key="sales_acq_revenue")

    st.markdown("#### Units sold by acquisition source over time")
    source_links(("", SALES_SHEET, "inventory_sales_df"))
    units_o = S.units_sold_by_month(sales, span, by="ownership")
    st.plotly_chart(
        _shared_xaxis(_line_by_group(units_o, "units", order, ACQUISITION_COLORS,
                                     "Units", "Acquisition source")),
        use_container_width=True, key="sales_acq_units")

    totals = (sales.groupby("ownership")
                   .agg(revenue=("revenue", "sum"),
                        units=("units", "sum"))
                   .reset_index())
    if len(totals):
        st.markdown("#### Totals (selected range)")
        scols = st.columns(len(totals))
        for col, (_, row) in zip(scols, totals.iterrows()):
            label = "Consignment" if row["ownership"] == "consignment" else "DV-Owned"
            col.metric(f"{label} — revenue", f"${row['revenue']:,.0f}",
                       help=f"{row['units']:,.0f} units.")
