"""Sales page — Mack's headline metrics for instrument + bow sales, grouped
by month / instrument / bow / consignment-vs-DV-Owned, plus a clearly-
labeled Wholesale/Auction placeholder.

The page never computes metrics inline; everything routes through lib.sales
so definitions stay centralized and swappable.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import load_inventory_sales
from lib import sales as S
from lib.theme import (BROWN, GOLD, INSTRUMENT_COLORS, OWNERSHIP_COLORS,
                       PRODUCT_TYPE_COLORS, SAGE, SLATE, WARM_GRAY, WINE,
                       apply_theme)

st.set_page_config(page_title="Sales — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

# ──────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────
st.title("Sales")
st.caption("Instrument and bow sales — revenue, units, and the consignment / "
           "DV-owned split. Cash basis. Daily refresh from cleaned Google Sheets.")

with st.expander("Data notes — read once", expanded=False):
    st.markdown(
        """
        **Cash basis only.** QuickBooks emits a parallel accrual export but
        it isn't staged yet. Mack's "cash vs accrual" toggle from the spec is
        deferred until the accrual pipeline lands.

        **Units sold** = sum of `quantity` on rows where `payment_type ==
        'full/final payment'`. This avoids counting installment payments
        multiple times (a $80k cello paid over six months settles *once*
        on its final payment) while preserving batch quantities on
        single-row sales (a wholesale row carrying `quantity=5` contributes
        5). Final-payment rows with no `quantity` are read as 1 unit.

        **Bow sales — high-tier only.** Bows surfaced here are the
        instrument-grade bows flowing through the Instrument / Consignment
        distribution accounts. Lower-tier accessory bows are booked under
        `Sales of Product Income` (a separate `product_sales_df` tab) and
        are NOT included in this view yet.

        **Consignment vs DV Owned** is derived upstream from
        `distribution_account`: `Consignment Income` /
        `Consignment Instrument Sales` → Consignment; `Instrument Sales` /
        `Inventory Instrument Sales` → DV Owned.

        **Wholesale & Auction views are placeholders.** Mack's spec splits
        DV Owned into Wholesale and Auction sub-views, but the cleaned data
        isn't tagged with those categories yet — flagged in
        `09_known_issues:185` as "still need to add this view." The tab is
        included so the shape is visible; data will plug in once the
        classification lands.

        **Mack's open "other?" metric.** The spec leaves room for an
        additional metric beyond $ and units (e.g. average ticket, mix).
        Pending Mack's call — happy to add once defined.
        """
    )

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters
# ──────────────────────────────────────────────────────────────────────────
sales_all = load_inventory_sales()
all_months = S.monthly_span(sales_all)
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
    help="Some rows lack instrument metadata (memo too generic); "
         "deselect 'unknown' to exclude them.",
)
sel_product = st.sidebar.radio(
    "Product type",
    options=["Both", "Instruments only", "Bows only"],
    index=0,
    help="Instrument-grade bows are tagged via memo regex; high-tier only "
         "(accessory bows in product_sales_df are out of scope here).",
)
sel_ownership = st.sidebar.radio(
    "Ownership",
    options=["Both", "DV Owned only", "Consignment only"],
    index=0,
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= pd.Period(sel_start))
              & (df["month"] <= pd.Period(sel_end))]


def by_instrument(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["instrument"].isin(sel_instruments)] if sel_instruments else df.iloc[0:0]


def by_product(df: pd.DataFrame) -> pd.DataFrame:
    if sel_product == "Instruments only":
        return df[~df["bow"]]
    if sel_product == "Bows only":
        return df[df["bow"]]
    return df


def by_ownership(df: pd.DataFrame) -> pd.DataFrame:
    if sel_ownership == "DV Owned only":
        return df[df["ownership"] == "dv_owned"]
    if sel_ownership == "Consignment only":
        return df[df["ownership"] == "consignment"]
    return df


sales = by_ownership(by_product(by_instrument(in_range(sales_all))))
span = S.monthly_span(sales) if len(sales) else all_months

# ──────────────────────────────────────────────────────────────────────────
# KPI row
# ──────────────────────────────────────────────────────────────────────────
kpi = S.kpi_snapshot(sales, span)
st.subheader(f"As of {kpi['as_of']}")

c1, c2, c3, c4 = st.columns(4)
rev, rev_d = kpi["revenue"]
units, units_d = kpi["units"]
c1.metric("Revenue (this month)", f"${rev:,.0f}",
          f"{rev_d:+,.0f} vs prior mo")
c2.metric("Units sold (this month)", f"{units:,.0f}",
          f"{units_d:+,.0f} vs prior mo")
c3.metric("All-time revenue", f"${kpi['all_time_revenue']:,.0f}",
          help="Sum across the filtered month range.")
c4.metric("All-time units", f"{kpi['all_time_units']:,.0f}",
          help="Sum across the filtered month range. "
               "Counts each sale once on its final-payment month.")

st.caption("Latest month may be partial — figures update daily.")

# ──────────────────────────────────────────────────────────────────────────
# Chart helpers
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


def _revenue_units_combo(df_rev: pd.DataFrame, df_units: pd.DataFrame,
                          rev_color: str = SAGE,
                          units_color: str = BROWN) -> go.Figure:
    """Bars for revenue ($) + line for units, secondary y-axis."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_rev["month"], y=df_rev["revenue"], name="Revenue",
                         marker_color=rev_color,
                         hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}"
                                       "<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=df_units["month"], y=df_units["units"],
                             name="Units sold", mode="lines+markers",
                             line=dict(color=units_color, width=2.5),
                             hovertemplate="%{x|%b %Y}<br>Units: %{y:,.0f}"
                                           "<extra></extra>"),
                  secondary_y=True)
    fig.update_yaxes(title_text="$", tickprefix="$", tickformat=",.0f",
                     secondary_y=False)
    fig.update_yaxes(title_text="Units", secondary_y=True)
    fig.update_layout(height=400)
    return fig


# ──────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────
tab_overview, tab_instr, tab_bows, tab_own, tab_wholesale = st.tabs(
    ["Overview", "By Instrument", "Bows",
     "Consignment vs DV Owned", "Wholesale / Auction (placeholder)"]
)

# ── Overview ──────────────────────────────────────────────────────────────
with tab_overview:
    st.markdown("#### Monthly revenue and units sold")
    rev = S.revenue_by_month(sales, span)
    units = S.units_sold_by_month(sales, span)
    st.plotly_chart(_shared_xaxis(_revenue_units_combo(rev, units)),
                    use_container_width=True)
    st.caption("Bars = revenue (cash received this month). Line = units sold "
               "(sales that closed this month). The two diverge for "
               "installment sales — revenue trickles in over months, units "
               "only register on the final payment.")

# ── By Instrument ─────────────────────────────────────────────────────────
with tab_instr:
    st.info("Bows are excluded from this tab so the violin/viola/cello "
            "comparison is apples-to-apples. See the **Bows** tab for the "
            "bow split.", icon="ℹ️")
    instr_sales = S.instruments_only(sales)

    st.markdown("#### Revenue by instrument")
    rev_i = S.revenue_by_month(instr_sales, span, by="instrument")
    fig = px.bar(rev_i, x="month", y="revenue", color="group",
                 color_discrete_map={k.title(): v for k, v in INSTRUMENT_COLORS.items()},
                 labels={"revenue": "$", "group": "Instrument"})
    fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                      barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Units sold by instrument")
    units_i = S.units_sold_by_month(instr_sales, span, by="instrument")
    fig = px.bar(units_i, x="month", y="units", color="group",
                 color_discrete_map={k.title(): v for k, v in INSTRUMENT_COLORS.items()},
                 labels={"units": "Units", "group": "Instrument"})
    fig.update_layout(height=380, barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

# ── Bows ──────────────────────────────────────────────────────────────────
with tab_bows:
    bows = S.bows_only(sales)
    if len(bows) == 0:
        st.info("No bow rows in the current filter set. (Try widening the "
                "month range or selecting Product type = Both.)", icon="ℹ️")
    else:
        st.markdown("#### Bow revenue and units")
        rev_b = S.revenue_by_month(bows, span)
        units_b = S.units_sold_by_month(bows, span)
        st.plotly_chart(
            _shared_xaxis(_revenue_units_combo(rev_b, units_b,
                                                rev_color=GOLD,
                                                units_color=BROWN)),
            use_container_width=True,
        )

        st.markdown("#### Bow revenue by instrument family")
        rev_bi = S.revenue_by_month(bows, span, by="instrument")
        fig = px.bar(rev_bi, x="month", y="revenue", color="group",
                     color_discrete_map={k.title(): v for k, v in INSTRUMENT_COLORS.items()},
                     labels={"revenue": "$", "group": "Bow for"})
        fig.update_layout(height=350, yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                          barmode="stack")
        st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
        st.caption("Bow-for-instrument is detected from the memo (e.g. "
                   "'Carbon Composite Violin Bow' → violin). Generic bows "
                   "with no instrument family land in 'Unknown'.")

# ── Consignment vs DV Owned ───────────────────────────────────────────────
with tab_own:
    st.markdown("#### Revenue by ownership")
    rev_o = S.revenue_by_month(sales, span, by="ownership")
    fig = px.bar(rev_o, x="month", y="revenue", color="group",
                 color_discrete_map=OWNERSHIP_COLORS,
                 labels={"revenue": "$", "group": "Ownership"})
    fig.update_layout(height=380, yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                      barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    st.markdown("#### Units sold by ownership")
    units_o = S.units_sold_by_month(sales, span, by="ownership")
    fig = px.bar(units_o, x="month", y="units", color="group",
                 color_discrete_map=OWNERSHIP_COLORS,
                 labels={"units": "Units", "group": "Ownership"})
    fig.update_layout(height=380, barmode="stack")
    st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

    # Side stat: all-time totals per ownership
    totals = (sales.groupby("ownership")
                   .agg(revenue=("amount", "sum"),
                        rows=("amount", "size"))
                   .reset_index())
    if len(totals):
        st.markdown("#### All-time totals")
        cols = st.columns(len(totals))
        for col, (_, row) in zip(cols, totals.iterrows()):
            label = "Consignment" if row["ownership"] == "consignment" else "DV Owned"
            col.metric(f"{label} — revenue", f"${row['revenue']:,.0f}",
                       help=f"{int(row['rows']):,} payment rows.")

# ── Wholesale / Auction placeholder ───────────────────────────────────────
with tab_wholesale:
    st.warning("**Placeholder tab.** Mack's spec splits DV Owned into "
               "**Wholesale** and **Auction**, but the cleaned data doesn't "
               "carry those tags yet — flagged in "
               "`09_known_issues_and_todos.md:185` as *\"still need to add "
               "this view.\"* Once a Wholesale/Auction signal lands in "
               "`inventory_sales_df` (a column, a memo regex, or a "
               "customer-level mapping), this tab will plug in via "
               "`lib/sales.py` like the Ownership view.",
               icon="🚧")

    st.markdown("#### Shape this view will take (data not yet captured)")
    st.markdown(
        "- **DV Owned → Retail** (the default — sales to individual customers)\n"
        "- **DV Owned → Wholesale** (bulk sales to other shops / dealers)\n"
        "- **DV Owned → Auction** (sales through auction channels)\n\n"
        "Revenue and units would split exactly as in the "
        "*Consignment vs DV Owned* tab, scoped to DV-Owned rows only."
    )

    dv_owned_rows = int((sales["ownership"] == "dv_owned").sum())
    st.caption(f"Today there are {dv_owned_rows:,} DV-Owned payment rows in "
               "the current filter — all currently uncategorized at the "
               "Wholesale/Auction level.")
