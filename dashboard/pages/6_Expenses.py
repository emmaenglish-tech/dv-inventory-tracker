"""Expenses page — operating spend, with fixed-monthly vs variable vs
infrequent emphasized (the split the owner asked for).

Thin renderer: every measure routes through ``lib.expenses`` over the
pre-aggregated ``expenses_monthly`` tab.

Owner draws / equity (negative-by-convention rows that can ride along in the
expense feed) are NOT operating costs, so they're excluded from every total
here via ``E.operating_only`` — see lib/expenses.py for the rationale and the
list of excluded categories.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import load_expenses_monthly
from lib import expenses as E
from lib.filters import date_range_filter
from lib.theme import EXPENSE_CLASS_COLORS, apply_theme

st.set_page_config(page_title="Expenses — Denver Violins",
                   page_icon="🎻", layout="wide")
apply_theme()

st.title("Expenses")
st.caption("Operating spend, split by fixed-monthly, variable, and infrequent. "
           "Cash basis. Daily refresh from cleaned Google Sheets.")
st.caption("Owner draws and equity movements are excluded — these are operating "
           "expenses only.")

# ──────────────────────────────────────────────────────────────────────────
# Load + sidebar filters (date range persists across pages)
# ──────────────────────────────────────────────────────────────────────────
expenses_raw = load_expenses_monthly()
expenses_all = E.operating_only(expenses_raw)   # drop owner draw / equity

all_months = E.monthly_span(expenses_all)
start, end = date_range_filter(all_months)

sel_classes = st.sidebar.multiselect(
    "Expense class",
    options=["Fixed", "Variable", "Infrequent"],
    default=["Fixed", "Variable", "Infrequent"],
    help="Fixed = recurring monthly; Variable = scales with activity; "
         "Infrequent = one-off / irregular.",
)
_sel_classes_lower = {c.lower() for c in sel_classes}

all_categories = sorted(
    expenses_all["expense_category"].dropna().astype(str).unique().tolist())
sel_categories = st.sidebar.multiselect(
    "Expense category",
    options=all_categories,
    default=all_categories,
    help="Optional — deselect to focus on specific categories.",
)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["month"] >= start) & (df["month"] <= end)]


def by_class(df: pd.DataFrame) -> pd.DataFrame:
    if not sel_classes:
        return df.iloc[0:0]
    cls = df["expense_class"].astype(str).str.strip().str.lower()
    return df[cls.isin(_sel_classes_lower)]


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    if not all_categories:          # nothing to filter on yet (empty data)
        return df
    if not sel_categories:
        return df.iloc[0:0]
    return df[df["expense_category"].isin(sel_categories)]


expenses = by_category(by_class(in_range(expenses_all)))
span = E.monthly_span(expenses) if len(expenses) else (
    pd.period_range(start, end, freq="M") if len(all_months) else
    pd.PeriodIndex([], freq="M"))

if expenses_all.empty:
    st.info("No data yet — this report populates once the upstream aggregate "
            "is built.", icon="ℹ️")

# ──────────────────────────────────────────────────────────────────────────
# KPIs (reflect the selected date range): Total + one per class
# ──────────────────────────────────────────────────────────────────────────
kpi = E.kpi_snapshot(expenses, span)
st.subheader(f"Selected range — through {kpi['as_of']}")

c_total, c_fixed, c_var, c_infq = st.columns(4)
c_total.metric("Total Expenses", f"${kpi['total_amount']:,.0f}",
               help="Operating spend across the selected date range "
                    "(excludes owner draws / equity).")
class_totals = dict(kpi["by_class"])
c_fixed.metric("Fixed", f"${class_totals.get('Fixed', 0.0):,.0f}",
               help="Recurring monthly costs (rent, subscriptions, …).")
c_var.metric("Variable", f"${class_totals.get('Variable', 0.0):,.0f}",
             help="Costs that scale with activity.")
c_infq.metric("Infrequent", f"${class_totals.get('Infrequent', 0.0):,.0f}",
              help="One-off / irregular costs.")
st.caption("Totals reflect the selected date range. Latest month may be "
           "partial — figures update daily.")


# ──────────────────────────────────────────────────────────────────────────
# Chart helper
# ──────────────────────────────────────────────────────────────────────────
def _shared_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(dtick="M6", tickformat="%b %Y")
    fig.update_layout(hovermode="x unified")
    return fig


_CLASS_ORDER = ["Fixed", "Variable", "Infrequent"]

# ──────────────────────────────────────────────────────────────────────────
# Charts + table
# ──────────────────────────────────────────────────────────────────────────
st.markdown("#### Monthly expenses by class")
amt_cls = E.amount_by_month(expenses, span, by="expense_class")
fig = px.line(amt_cls, x="month", y="amount", color="group",
              color_discrete_map=EXPENSE_CLASS_COLORS,
              category_orders={"group": _CLASS_ORDER},
              labels={"amount": "$", "group": "Expense class"})
fig.update_traces(line=dict(width=2.5))
fig.update_layout(height=400, yaxis_tickprefix="$", yaxis_tickformat=",.0f")
st.plotly_chart(_shared_xaxis(fig), use_container_width=True)
st.caption("Fixed costs should read as a roughly flat baseline; variable rides "
           "with activity; infrequent shows up as occasional spikes.")

st.markdown("#### Total monthly expenses")
amt_total = E.amount_by_month(expenses, span)
fig = go.Figure(go.Bar(x=amt_total["month"], y=amt_total["amount"],
                       name="Expenses", marker_color=EXPENSE_CLASS_COLORS["Fixed"],
                       hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"))
fig.update_layout(height=340, yaxis_title="$", yaxis_tickprefix="$",
                  yaxis_tickformat=",.0f", showlegend=False)
st.plotly_chart(_shared_xaxis(fig), use_container_width=True)

st.markdown("#### Breakdown by category")
breakdown = E.category_breakdown(expenses)
if not len(breakdown):
    st.info("No expenses in the current filter set.", icon="ℹ️")
else:
    st.dataframe(
        breakdown,
        hide_index=True,
        use_container_width=True,
        column_config={
            "expense_category": st.column_config.TextColumn("Category"),
            "expense_class": st.column_config.TextColumn("Class"),
            "amount": st.column_config.NumberColumn("Amount", format="$%.0f"),
            "transactions": st.column_config.NumberColumn(
                "Transactions", format="%d"),
            "amount_share": st.column_config.ProgressColumn(
                "Share of spend", min_value=0.0,
                max_value=float(breakdown["amount_share"].max() or 1.0),
                format="%.1f%%"),
        },
    )
