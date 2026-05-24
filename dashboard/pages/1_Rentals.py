"""Rentals page — Mack's five headline metrics, grouped by month / instrument
/ high-end vs regular, plus a revenue-vs-cost view and a clearly-labeled
delinquency placeholder.

Thin renderer: owned/rented/available come from the precomputed
``rentals_inventory`` cut grid (distinct-customer "rented" isn't additive, so
each cut is materialized upstream); revenue/cost/delinquency are summed from
the additive ``rentals_monthly`` flows. The instrument filter is single-select
so every owned/rented/available view maps to a precomputed cut.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import (load_rentals_bows, load_rentals_inventory,
                      load_rentals_monthly)
from lib import rentals as R
from lib.theme import (BROWN, GOLD, INSTRUMENT_COLORS, SAGE, SCOPE_COLORS,
                       SLATE, WINE, apply_theme)

st.set_page_config(page_title="Rentals — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

st.title("Rentals")
st.caption("Inventory, rental activity, revenue vs cost, and delinquency. "
           "Reads the daily aggregate sheet.")

with st.expander("Data notes — read once", expanded=False):
    st.markdown(
        """
        **Owned** counts only fleet entries in QB purchase data (rentable
        violin/viola/cello; rental bows and accessory parts excluded). Pre-2023
        the fleet was under-captured, so historical **Available** reads
        negative; recent months sit near zero after Mack's 2026-05-19 ledger
        corrections.

        **Rented** is duration-aware: an annual payment carries 12 months, a
        monthly/prorated payment 1 month. Counted as distinct customers in
        coverage that month. Because it's a distinct count it is **not additive
        across instruments/scope**, so each cut is precomputed upstream — the
        instrument filter is single-select for that reason.

        **Available = Owned − Rented**, surfaced raw.

        **High-End vs Regular** detection is sparse in the source data; almost
        everything falls under "Regular".

        **Delinquency** is a **placeholder** — late-fee rows only, pending
        Mack's full definition.

        Every number here is the raw monthly rollup in
        `clean_datasets_dashboard_aggregates` — open it to drill in.
        """
    )

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
inv_all = load_rentals_inventory()
flows_all = load_rentals_monthly()
bows_all = load_rentals_bows()
all_months = R.monthly_span(inv_all, flows_all, bows_all)
month_strings = [str(m) for m in all_months]

st.sidebar.header("Filters")
sel_start, sel_end = st.sidebar.select_slider(
    "Month range",
    options=month_strings,
    value=(month_strings[0], month_strings[-1]),
)
sel_instrument = st.sidebar.selectbox(
    "Instrument",
    options=["All", "Violin", "Viola", "Cello", "Unknown"],
    index=0,
    help="Single-select: distinct-customer 'rented' isn't additive across "
         "instruments, so each cut is precomputed upstream.",
)
sel_scope = st.sidebar.radio(
    "Scope",
    options=["Both", "Regular only", "High-End only"],
    index=0,
    help="High-end detection is sparse; 'High-End only' will be nearly empty.",
)

span = pd.period_range(pd.Period(sel_start), pd.Period(sel_end), freq="M")
instr_cut = "all" if sel_instrument == "All" else sel_instrument.lower()
scope_cut = {"Both": "all", "Regular only": "regular",
             "High-End only": "high_end"}[sel_scope]


def filter_flows(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df["month"] >= pd.Period(sel_start)) & (df["month"] <= pd.Period(sel_end))]
    if instr_cut != "all":
        df = df[df["instrument"] == instr_cut]
    if scope_cut == "regular":
        df = df[~df["high_end_rental"]]
    elif scope_cut == "high_end":
        df = df[df["high_end_rental"]]
    return df


flows = filter_flows(flows_all)
bows_in_range = bows_all[(bows_all["month"] >= pd.Period(sel_start))
                         & (bows_all["month"] <= pd.Period(sel_end))]

# ──────────────────────────────────────────────────────────────────────────
# KPI row
# ──────────────────────────────────────────────────────────────────────────
kpi = R.kpi_snapshot(inv_all, flows, span, instr_cut, scope_cut)
st.subheader(f"As of {kpi['as_of']}")

c1, c2, c3, c4, c5, c6 = st.columns(6)
o, od = kpi["owned"]
r, rd = kpi["rented"]
a, ad = kpi["available"]
dc, dcd = kpi["delinquent_count"]
dv, dvd = kpi["delinquent_value"]
c1.metric("Owned (instruments)", f"{int(o)}", f"{int(od):+d} vs prior mo")
c2.metric("Rented", f"{int(r)}", f"{int(rd):+d} vs prior mo")
c3.metric("Available", f"{int(a)}", f"{int(ad):+d} vs prior mo")
c4.metric("Delinquent (count) ⚠︎", f"{int(dc)}", f"{int(dcd):+d}",
          help="PLACEHOLDER — late-fee rows only.")
c5.metric("Delinquent ($) ⚠︎", f"${dv:,.0f}", f"{dvd:+,.0f}",
          help="PLACEHOLDER — late-fee rows only. Delta in $.")
c6.metric("Rental bows", f"{R.bows_owned_total(bows_in_range)}",
          help="Separate shop-wide fleet category (Mack's split); not split by "
               "instrument/scope.")

st.caption("⚠︎ = placeholder metric pending Mack's full delinquency definition.")


# ──────────────────────────────────────────────────────────────────────────
# Helpers for charts
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


_INSTR_CMAP = {k.title(): v for k, v in INSTRUMENT_COLORS.items()}

# ──────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────
tab_overview, tab_instr, tab_scope, tab_rev, tab_delinq = st.tabs(
    ["Overview", "By Instrument", "High-End vs Regular",
     "Revenue vs Cost", "Delinquency (placeholder)"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    cut = R.inventory_for_cut(inv_all, span, instr_cut, scope_cut)
    st.markdown("#### Owned vs Rented")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cut["month"], y=cut["owned"],
                             name="Owned (cumulative)", mode="lines",
                             line=dict(color=SLATE, width=3)))
    fig.add_trace(go.Scatter(x=cut["month"], y=cut["rented"],
                             name="Rented (duration-aware)", mode="lines",
                             line=dict(color=BROWN, width=3)))
    fig.update_layout(height=380, yaxis_title="Instruments")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Available (Owned − Rented)")
    colors = [SAGE if v >= 0 else WINE for v in cut["available"]]
    fig = go.Figure(go.Bar(x=cut["month"], y=cut["available"],
                           marker_color=colors,
                           hovertemplate="%{x|%b %Y}<br>Available: %{y}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#8A8378", width=1))
    fig.update_layout(height=300, yaxis_title="Instruments", showlegend=False)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
    st.caption("Negative bars are mostly historical (pre-2023 ledger gap); "
               "recent months sit at/near zero.")

# ── By Instrument ─────────────────────────────────────────────────────────
with tab_instr:
    st.caption("Breakdown shows all instruments regardless of the instrument "
               "filter (the filter drives the Overview + KPI cards).")
    st.markdown("#### Owned by instrument (cumulative)")
    o_by_i = R.inventory_by_instrument(inv_all, span, "owned", scope=scope_cut)
    fig = px.area(o_by_i, x="month", y="owned", color="group",
                  color_discrete_map=_INSTR_CMAP,
                  labels={"owned": "Instruments", "group": "Instrument"})
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Rented by instrument")
    r_by_i = R.inventory_by_instrument(inv_all, span, "rented", scope=scope_cut)
    fig = px.line(r_by_i, x="month", y="rented", color="group",
                  color_discrete_map=_INSTR_CMAP,
                  labels={"rented": "Customers", "group": "Instrument"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
    st.caption("'Unknown' is large because many income rows don't carry "
               "instrument metadata — improving extraction is future work.")

# ── High-End vs Regular ───────────────────────────────────────────────────
with tab_scope:
    st.info("Detection is sparse in the source data; almost everything falls "
            "under 'Regular'.", icon="ℹ️")
    st.markdown("#### Owned by scope (cumulative)")
    o_by_s = R.inventory_by_scope(inv_all, span, "owned", instrument=instr_cut)
    fig = px.area(o_by_s, x="month", y="owned", color="group",
                  color_discrete_map=SCOPE_COLORS,
                  labels={"owned": "Instruments", "group": "Scope"})
    fig.update_layout(height=350)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Rented by scope")
    r_by_s = R.inventory_by_scope(inv_all, span, "rented", instrument=instr_cut)
    fig = px.line(r_by_s, x="month", y="rented", color="group",
                  color_discrete_map=SCOPE_COLORS,
                  labels={"rented": "Customers", "group": "Scope"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=350)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

# ── Revenue vs Cost ───────────────────────────────────────────────────────
with tab_rev:
    rvc = R.revenue_vs_cost_by_month(flows, span)
    st.markdown("#### Monthly rental revenue vs fleet cost")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rvc["month"], y=rvc["revenue"], name="Revenue",
                         marker_color=SAGE,
                         hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(x=rvc["month"], y=rvc["cost"], name="Fleet cost",
                         marker_color=WINE,
                         hovertemplate="%{x|%b %Y}<br>Cost: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(barmode="group", height=380, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Cumulative revenue vs cost")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rvc["month"], y=rvc["cum_revenue"],
                             name="Cumulative revenue", mode="lines",
                             line=dict(color=SAGE, width=3),
                             fill="tozeroy", fillcolor="rgba(122,158,126,0.15)"))
    fig.add_trace(go.Scatter(x=rvc["month"], y=rvc["cum_cost"],
                             name="Cumulative cost", mode="lines",
                             line=dict(color=WINE, width=3),
                             fill="tozeroy", fillcolor="rgba(158,75,59,0.15)"))
    fig.update_layout(height=380, yaxis_title="$",
                      yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    total_rev = rvc["cum_revenue"].iloc[-1] if len(rvc) else 0.0
    total_cost = rvc["cum_cost"].iloc[-1] if len(rvc) else 0.0
    m1, m2, m3 = st.columns(3)
    m1.metric("Rental revenue (range)", f"${total_rev:,.0f}")
    m2.metric("Fleet cost (range)", f"${total_cost:,.0f}")
    m3.metric("Net (revenue − cost)", f"${total_rev - total_cost:,.0f}")

# ── Delinquency placeholder ───────────────────────────────────────────────
with tab_delinq:
    st.warning("**Placeholder definition.** Counts late-fee rows only. Pending "
               "Mack's real delinquency definition; the chart shape is what she "
               "asked for, and the data swaps in upstream once defined.",
               icon="🚧")
    dq = R.delinquency_by_month(flows, span)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=dq["month"], y=dq["delinquent_count"],
                         name="Delinquent count", marker_color=WINE,
                         hovertemplate="%{x|%b %Y}<br>Count: %{y}<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=dq["month"], y=dq["delinquent_value"],
                             name="Delinquent $", mode="lines+markers",
                             line=dict(color=GOLD, width=2.5),
                             hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text="Count", secondary_y=False)
    fig.update_yaxes(title_text="$", tickprefix="$", tickformat=",.0f",
                     secondary_y=True)
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
