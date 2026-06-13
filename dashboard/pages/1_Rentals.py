"""Rentals page — fleet inventory, rental revenue vs cost, and delinquency.

Owned / rented / available come from the precomputed ``rentals_inventory`` cut
grid (distinct-customer "rented" isn't additive, so each cut is materialized
upstream); revenue / cost / delinquency are summed from the additive
``rentals_monthly`` flows. The instrument filter is single-select so every
inventory view maps to a precomputed cut.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import (global_monthly_span, load_rentals_bows,
                      load_rentals_inventory, load_rentals_monthly)
from lib.filters import date_range_filter
from lib import rentals as R
from lib.theme import (INSTRUMENT_GROUP_COLORS, SAGE, SLATE, WINE, apply_theme)

st.set_page_config(page_title="Rentals — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

st.title("Rentals")
st.caption("Fleet inventory, rental revenue vs cost, and delinquency.")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
inv_all = load_rentals_inventory()
flows_all = load_rentals_monthly()
bows_all = load_rentals_bows()
all_months = global_monthly_span()

st.sidebar.header("Filters")
sel_start, sel_end = date_range_filter(all_months)
sel_instrument = st.sidebar.selectbox(
    "Instrument type",
    options=["All", "Violin", "Viola", "Cello"],
    index=0,
    help="Single-select: distinct-customer 'rented' isn't additive across "
         "instruments, so each cut is precomputed upstream.",
)
sel_scope = st.sidebar.radio(
    "High End vs Standard",
    options=["Both", "Standard only", "High End only"],
    index=0,
)

span = pd.period_range(sel_start, sel_end, freq="M")
instr_cut = "all" if sel_instrument == "All" else sel_instrument.lower()
scope_cut = {"Both": "all", "Standard only": "regular",
             "High End only": "high_end"}[sel_scope]


def filter_flows(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df["month"] >= sel_start) & (df["month"] <= sel_end)]
    if instr_cut != "all":
        df = df[df["instrument"] == instr_cut]
    if scope_cut == "regular":
        df = df[~df["high_end_rental"]]
    elif scope_cut == "high_end":
        df = df[df["high_end_rental"]]
    return df


flows = filter_flows(flows_all)
rvc = R.revenue_vs_cost_by_month(flows, span)
total_rev = float(rvc["cum_revenue"].iloc[-1]) if len(rvc) else 0.0

# ──────────────────────────────────────────────────────────────────────────
# BANs — rental revenue over the selected range; inventory as of today
# ──────────────────────────────────────────────────────────────────────────
fleet = R.fleet_snapshot(inv_all, flows, span, scope=scope_cut)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total rental revenue (selected range)", f"${total_rev:,.0f}")
c2.metric("% of fleet rented (as of today)", f"{fleet['pct_rented'] * 100:.0f}%")
c3.metric("Total fleet size (as of today)", f"{int(fleet['owned'])}")
c4.metric("Total fleet cost (as of today)", f"${fleet['cum_cost']:,.0f}")

a = fleet["available"]
c5, c6, c7 = st.columns(3)
c5.metric("Violins available (as of today)", f"{int(a['violin'])}")
c6.metric("Violas available (as of today)", f"{int(a['viola'])}")
c7.metric("Cellos available (as of today)", f"{int(a['cello'])}")

st.caption(f"Inventory metrics are as of {fleet['as_of']} (latest month in the "
           "selected range).")


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
tab_overview, tab_instr, tab_rev, tab_delinq = st.tabs(
    ["Overview", "By Instrument", "Revenue vs Cost", "Delinquency"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    cut = R.inventory_for_cut(inv_all, span, instr_cut, scope_cut)

    st.markdown("#### Fleet owned vs rented over time")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cut["month"], y=cut["owned"],
                             name="Owned", mode="lines",
                             line=dict(color=SLATE, width=3)))
    fig.add_trace(go.Scatter(x=cut["month"], y=cut["rented"],
                             name="Rented", mode="lines",
                             line=dict(color=WINE, width=3)))
    fig.update_layout(height=380, yaxis_title="Instruments")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="rentals_owned_vs_rented")

    st.markdown("#### Available (Owned − Rented) over time")
    fig = go.Figure(go.Scatter(
        x=cut["month"], y=cut["available"], mode="lines",
        line=dict(color=SAGE, width=3), name="Available",
        hovertemplate="%{x|%b %Y}<br>Available: %{y}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#8A8378", width=1))
    fig.update_layout(height=320, yaxis_title="Instruments", showlegend=False)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="rentals_available")
    st.caption("Negative values are historical (pre-2023 fleet under-capture); "
               "recent months sit at or near zero.")

# ── By Instrument ─────────────────────────────────────────────────────────
with tab_instr:
    st.caption("Breakdown shows all instruments regardless of the instrument "
               "filter (the filter drives the Overview and the metric cards).")

    st.markdown("#### Owned by instrument over time")
    o_by_i = R.inventory_by_instrument(inv_all, span, "owned", scope=scope_cut)
    fig = px.line(o_by_i, x="month", y="owned", color="group",
                  color_discrete_map=INSTRUMENT_GROUP_COLORS,
                  labels={"owned": "Instruments", "group": "Instrument"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="rentals_owned_by_instrument")

    st.markdown("#### Rented by instrument over time")
    r_by_i = R.inventory_by_instrument(inv_all, span, "rented", scope=scope_cut)
    r_by_i = r_by_i[r_by_i["group"] != "Unknown"]
    fig = px.line(r_by_i, x="month", y="rented", color="group",
                  color_discrete_map=INSTRUMENT_GROUP_COLORS,
                  labels={"rented": "Customers", "group": "Instrument"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="rentals_rented_by_instrument")

# ── Revenue vs Cost ───────────────────────────────────────────────────────
with tab_rev:
    st.markdown("#### Cumulative rental revenue vs fleet cost")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rvc["month"], y=rvc["cum_revenue"],
                             name="Cumulative revenue", mode="lines",
                             line=dict(color=SAGE, width=3),
                             fill="tozeroy", fillcolor="rgba(122,158,126,0.15)"))
    fig.add_trace(go.Scatter(x=rvc["month"], y=rvc["cum_cost"],
                             name="Cumulative cost", mode="lines",
                             line=dict(color=WINE, width=3),
                             fill="tozeroy", fillcolor="rgba(158,75,59,0.15)"))
    fig.update_layout(height=400, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True,
                    key="rentals_cum_rev_vs_cost")

    total_cost = float(rvc["cum_cost"].iloc[-1]) if len(rvc) else 0.0
    m1, m2, m3 = st.columns(3)
    m1.metric("Rental revenue (selected range)", f"${total_rev:,.0f}")
    m2.metric("Fleet cost (selected range)", f"${total_cost:,.0f}")
    m3.metric("Net (revenue − cost)", f"${total_rev - total_cost:,.0f}")

# ── Delinquency ───────────────────────────────────────────────────────────
with tab_delinq:
    dq = R.delinquency_by_month(flows, span)
    total_count = int(dq["delinquent_count"].sum())
    total_value = float(dq["delinquent_value"].sum())

    d1, d2 = st.columns(2)
    d1.metric("Total inventory delinquent (selected range)", f"{total_count}")
    d2.metric("Total value of delinquency (selected range)", f"${total_value:,.0f}")

    detail = dq[dq["delinquent_count"] > 0].copy()
    if not len(detail):
        st.caption("No delinquencies in the selected range.")
    else:
        detail["Month"] = detail["month"].dt.strftime("%b %Y")
        st.dataframe(
            detail[["Month", "delinquent_count", "delinquent_value"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "delinquent_count": st.column_config.NumberColumn(
                    "Delinquent count", format="%d"),
                "delinquent_value": st.column_config.NumberColumn(
                    "Delinquent value", format="$%.0f"),
            },
        )
    st.caption("Delinquency definition is provisional pending finalized "
               "criteria.")
