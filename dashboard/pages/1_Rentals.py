"""Rentals page — Mack's five headline metrics, grouped by month / instrument
/ high-end vs regular, plus a revenue-vs-cost view and a clearly-labeled
delinquency placeholder.

The page never computes metrics inline; everything routes through lib.rentals
so definitions stay centralized and swappable.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import load_rental_fleet, load_rental_income
from lib import rentals as R
from lib.theme import (BROWN, GOLD, INSTRUMENT_COLORS, SAGE, SCOPE_COLORS,
                       SLATE, STATE_COLORS, WARM_GRAY, WINE, apply_theme)

st.set_page_config(page_title="Rentals — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

# ──────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────
st.title("Rentals")
st.caption("Inventory, rental activity, revenue vs cost, and delinquency. "
           "Data refreshes daily from the cleaned Google Sheets.")

with st.expander("Data notes — read once", expanded=False):
    st.markdown(
        """
        **Owned** counts only fleet entries in QB purchase data. Pre-2023 the
        fleet was under-captured (only **12** instruments recorded by end of
        2022, while ~77 customers began renting). Mack's three corrections
        (2026-05-19) — parenthetical counts, leading-integer counts, and
        excluding accessory parts (cases / fingerboards / bags) — closed most
        of the gap. Historical Available will still read negative; recent
        months sit near zero.

        **Rented** is duration-aware: an annual payment carries 12 months, a
        monthly/prorated payment 1 month. Counted as distinct customers in
        coverage that month (≈ one agreement per customer). Deposits and
        insurance fees are excluded — no double-counting with rental_fee.

        **Available = Owned − Rented.** Surfaced raw; recent months are nearly
        aligned, the historical negative reflects the pre-2023 capture gap.

        **High-End vs Regular** detection is sparse (1 of 123 fleet rows, 9 of
        6,448 income rows). The grouping is included as Mack requested but
        most rentals fall under "Regular". Improving detection is future work.

        **Delinquency** is a **placeholder** — late-fee rows only. Pending
        Mack's full definition (e.g. unpaid expected rent, days past due).

        **Known staging bug** (logged): some "Rental Deposit (deleted)" rows
        are labelled `rental_fee` upstream — excluded here via a product_service
        check.
        """
    )

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
fleet_all = load_rental_fleet()
income_all = load_rental_income()
all_months = R.monthly_span(fleet_all, income_all)
month_strings = [str(m) for m in all_months]

st.sidebar.header("Filters")
sel_start, sel_end = st.sidebar.select_slider(
    "Month range",
    options=month_strings,
    value=(month_strings[0], month_strings[-1]),
)
sel_instruments = st.sidebar.multiselect(
    "Instrument type",
    options=["violin", "viola", "cello", "unknown"],
    default=["violin", "viola", "cello", "unknown"],
    help="46% of income rows lack instrument metadata — deselecting 'unknown' "
         "will drop most rental activity from charts.",
)
sel_scope = st.sidebar.radio(
    "Scope",
    options=["Both", "Regular only", "High-End only"],
    index=0,
    help="High-end detection is sparse; 'High-End only' will be nearly empty.",
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= pd.Period(sel_start))
              & (df["month"] <= pd.Period(sel_end))]


def by_scope(df: pd.DataFrame) -> pd.DataFrame:
    if sel_scope == "High-End only":
        return df[df["high_end_rental"]]
    if sel_scope == "Regular only":
        return df[~df["high_end_rental"]]
    return df


def by_instrument(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["instrument"].isin(sel_instruments)] if sel_instruments else df.iloc[0:0]


fleet = by_instrument(by_scope(in_range(fleet_all)))
income = by_instrument(by_scope(in_range(income_all)))
span = R.monthly_span(fleet, income) if len(fleet) or len(income) else all_months

# ──────────────────────────────────────────────────────────────────────────
# KPI row
# ──────────────────────────────────────────────────────────────────────────
kpi = R.kpi_snapshot(fleet, income, span)
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
c6.metric("Rental bows", f"{R.bows_owned_total(fleet)}",
          help="Separate fleet category (Mack's split).")

st.caption("⚠︎ = placeholder metric pending Mack's full delinquency definition.")

# ──────────────────────────────────────────────────────────────────────────
# Helpers for charts
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


# ──────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────
tab_overview, tab_instr, tab_scope, tab_rev, tab_delinq = st.tabs(
    ["Overview", "By Instrument", "High-End vs Regular",
     "Revenue vs Cost", "Delinquency (placeholder)"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    st.markdown("#### Owned vs Rented")
    owned = R.owned_by_month(fleet, span)
    rented = R.rented_by_month(income, span)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=owned["month"], y=owned["owned"],
                             name="Owned (cumulative)", mode="lines",
                             line=dict(color=SLATE, width=3)))
    fig.add_trace(go.Scatter(x=rented["month"], y=rented["rented"],
                             name="Rented (duration-aware)", mode="lines",
                             line=dict(color=BROWN, width=3)))
    fig.update_layout(height=380, yaxis_title="Instruments")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Available (Owned − Rented)")
    avail = R.available_by_month(fleet, income, span)
    colors = [SAGE if v >= 0 else WINE for v in avail["available"]]
    fig = go.Figure(go.Bar(x=avail["month"], y=avail["available"],
                           marker_color=colors,
                           hovertemplate="%{x|%b %Y}<br>Available: %{y}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#8A8378", width=1))
    fig.update_layout(height=300, yaxis_title="Instruments",
                      showlegend=False)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
    st.caption("Negative bars are mostly historical (2021–22 ledger frozen "
               "at 12 instruments). Recent months sit at/near zero after "
               "Mack's 2026-05-19 ledger corrections.")

# ── By Instrument ─────────────────────────────────────────────────────────
with tab_instr:
    st.markdown("#### Owned by instrument (cumulative)")
    o_by_i = R.owned_by_month(fleet, span, by="instrument")
    fig = px.area(o_by_i, x="month", y="owned", color="group",
                  color_discrete_map={k.title(): v for k, v in INSTRUMENT_COLORS.items()},
                  labels={"owned": "Instruments", "group": "Instrument"})
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Rented by instrument")
    r_by_i = R.rented_by_month(income, span, by="instrument")
    fig = px.line(r_by_i, x="month", y="rented", color="group",
                  color_discrete_map={k.title(): v for k, v in INSTRUMENT_COLORS.items()},
                  labels={"rented": "Customers", "group": "Instrument"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=380)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
    st.caption("'Unknown' is large because 46% of income rows don't carry "
               "instrument metadata in product_service — improving extraction "
               "is future work.")

# ── High-End vs Regular ───────────────────────────────────────────────────
with tab_scope:
    st.info("Detection sparse: only 1 of 123 fleet rows and 9 of 6,448 income "
            "rows are tagged high-end in the source data. The split is shown "
            "as Mack requested; almost everything falls under 'Regular'.",
            icon="ℹ️")
    st.markdown("#### Owned by scope (cumulative)")
    o_by_s = R.owned_by_month(fleet, span, by="high_end_rental")
    fig = px.area(o_by_s, x="month", y="owned", color="group",
                  color_discrete_map=SCOPE_COLORS,
                  labels={"owned": "Instruments", "group": "Scope"})
    fig.update_layout(height=350)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Rented by scope")
    r_by_s = R.rented_by_month(income, span, by="high_end_rental")
    fig = px.line(r_by_s, x="month", y="rented", color="group",
                  color_discrete_map=SCOPE_COLORS,
                  labels={"rented": "Customers", "group": "Scope"})
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(height=350)
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

# ── Revenue vs Cost ───────────────────────────────────────────────────────
with tab_rev:
    rvc = R.revenue_vs_cost_by_month(income, fleet, span)
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

    total_rev = rvc["cum_revenue"].iloc[-1]
    total_cost = rvc["cum_cost"].iloc[-1]
    margin = total_rev - total_cost
    m1, m2, m3 = st.columns(3)
    m1.metric("All-time rental revenue", f"${total_rev:,.0f}")
    m2.metric("All-time fleet cost", f"${total_cost:,.0f}")
    m3.metric("Net (revenue − cost)", f"${margin:,.0f}")

# ── Delinquency placeholder ───────────────────────────────────────────────
with tab_delinq:
    st.warning("**Placeholder definition.** Counts the 49 late-fee rows only. "
               "Pending Mack's real delinquency definition (e.g. customers "
               "with unpaid expected rent, days past due, value owed). The "
               "shape of the chart is what Mack asked for; the data will be "
               "swapped in lib/rentals.py:delinquency_placeholder_by_month "
               "once the definition lands.",
               icon="🚧")

    dq = R.delinquency_placeholder_by_month(income, span)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=dq["month"], y=dq["delinquent_count"],
                         name="Delinquent count",
                         marker_color=WINE,
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
