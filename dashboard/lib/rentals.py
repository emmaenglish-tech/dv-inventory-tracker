"""Rental metric definitions — the single source of truth for *what the
numbers mean*. Every chart/KPI on the Rentals page calls these; nothing
computes a metric inline. When Mack refines a definition, it changes here
and nowhere else.

Pure functions: a (filtered) DataFrame in, a tidy DataFrame out. No Streamlit,
no I/O — so they're trivially testable and cache-friendly.

Definitions
-----------
Owned       Cumulative count of fleet instruments acquired, by month.
            Restricted to rentable instruments (violin/viola/cello). Excluded:
            rental bows (``bow``), accessory parts that happen to name an
            instrument (``accessory``: cases, fingerboards, bags, …), and the
            rosin/cloths/bank-feed noise the staging layer leaves as ``unknown``.
Rented      Duration-aware. A rental_fee payment makes that customer "rented"
            for the month paid; an *annual* payment covers 12 months. Counted
            as distinct customers per month (≈ one rental agreement/customer
            in a small shop). Deposits and refund reversals don't count.
Available   Owned − Rented. Can read negative where fleet capture lags real
            stock; surfaced honestly rather than clamped.
Delinquent  PLACEHOLDER — late-fee rows only, pending Mack's real definition.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RENTABLE = ("violin", "viola", "cello")
_REVENUE_TYPES = ("rental_fee", "late_fee", "insurance_fee")  # deposits are a liability


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    """Continuous month index spanning every frame — the shared x-axis, so
    every chart lines up even when a frame has gaps."""
    months = pd.concat([f["month"].dropna() for f in frames if len(f)])
    return pd.period_range(months.min(), months.max(), freq="M")


def _tidy(grouped: pd.Series, span: pd.PeriodIndex, by: str | None,
          value_name: str, cumulative: bool = False) -> pd.DataFrame:
    """Reindex a (month[, group]) groupby result onto the full span so absent
    months become explicit zeros, optionally cumulate, and return long form
    with a plot-friendly Timestamp ``month`` column."""
    if by:
        wide = grouped.unstack(by, fill_value=0).reindex(span, fill_value=0)
        if cumulative:
            wide = wide.cumsum()
        out = wide.reset_index(names="period").melt(
            id_vars="period", var_name="group", value_name=value_name)
        out["group"] = _label_groups(out["group"], by)
    else:
        ser = grouped.reindex(span, fill_value=0)
        if cumulative:
            ser = ser.cumsum()
        ser.index.name = "period"
        out = ser.rename(value_name).reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def _label_groups(values: pd.Series, by: str) -> pd.Series:
    if by == "high_end_rental":
        return np.where(values.astype(bool), "High-End", "Regular")
    return values.astype(str).str.title()


def _rentable_instruments(fleet: pd.DataFrame) -> pd.DataFrame:
    """Rentable instrument stock only: violin/viola/cello, excluding rental
    bows, accessory parts (cases/fingerboards/bags/…), and the rosin/cloths/
    bank-feed noise booked to the fleet account."""
    return fleet[fleet["instrument"].isin(RENTABLE)
                 & ~fleet["bow"] & ~fleet["accessory"]
                 & fleet["month"].notna()]


def owned_by_month(fleet: pd.DataFrame, span: pd.PeriodIndex,
                   by: str | None = None) -> pd.DataFrame:
    f = _rentable_instruments(fleet)
    keys = ["month"] + ([by] if by else [])
    grouped = f.groupby(keys, dropna=False)["unit_count"].sum()
    return _tidy(grouped, span, by, "owned", cumulative=True)


def bows_owned_total(fleet: pd.DataFrame) -> int:
    """Rental bows are fleet stock too, but a separate category from the
    instrument metrics (Mack's distinction). Reported as a side stat."""
    return int(fleet.loc[fleet["bow"] & fleet["month"].notna(), "unit_count"].sum())


def rented_by_month(income: pd.DataFrame, span: pd.PeriodIndex,
                    by: str | None = None) -> pd.DataFrame:
    """Duration-aware active rentals.

    The idiom worth learning here: build the *list of months each payment
    covers* (``period_range``), then ``explode`` so one row becomes one
    (payment, month) pair. After that, "rented in month M" is just a
    distinct-customer count per month — no manual loops.
    """
    rf = income[
        income["payment_type"].eq("rental_fee")
        & ~income["product_service"].str.contains("deposit", case=False, na=False)
        & (income["amount"] > 0)
        & income["month"].notna()
    ].copy()

    n_months = np.where(rf["duration"].eq("annual"), 12, 1)
    rf["covered"] = [
        pd.period_range(m, periods=n, freq="M")
        for m, n in zip(rf["month"], n_months)
    ]
    ex = rf.explode("covered")
    # Don't project rentals beyond the data horizon (an annual payment in the
    # last month shouldn't invent future "rented" inventory).
    ex = ex[(ex["covered"] >= span.min()) & (ex["covered"] <= span.max())]
    ex["month"] = ex["covered"].astype("period[M]")

    keys = ["month"] + ([by] if by else [])
    grouped = ex.groupby(keys, dropna=False)["customer_full_name"].nunique()
    return _tidy(grouped, span, by, "rented")


def available_by_month(fleet: pd.DataFrame, income: pd.DataFrame,
                        span: pd.PeriodIndex, by: str | None = None) -> pd.DataFrame:
    owned = owned_by_month(fleet, span, by)
    rented = rented_by_month(income, span, by)
    on = ["month"] + (["group"] if by else [])
    out = owned.merge(rented, on=on, how="outer").fillna({"owned": 0, "rented": 0})
    out["available"] = out["owned"] - out["rented"]
    return out.sort_values(on).reset_index(drop=True)


def revenue_vs_cost_by_month(income: pd.DataFrame, fleet: pd.DataFrame,
                             span: pd.PeriodIndex) -> pd.DataFrame:
    """Mack's "what have we made vs spent on rentals". Revenue = rental/late/
    insurance fees net of reversals (deposits excluded — they're a liability).
    Cost = what we paid to acquire fleet stock."""
    rev_src = income[
        income["payment_type"].isin(_REVENUE_TYPES)
        & ~income["product_service"].str.contains("deposit", case=False, na=False)
        & income["month"].notna()
    ]
    rev = rev_src.groupby("month")["amount"].sum()
    cost = fleet[fleet["month"].notna()].groupby("month")["amount"].sum()

    out = pd.DataFrame({
        "revenue": rev.reindex(span, fill_value=0.0),
        "cost": cost.reindex(span, fill_value=0.0),
    })
    out["cum_revenue"] = out["revenue"].cumsum()
    out["cum_cost"] = out["cost"].cumsum()
    return out.reset_index(names="period").assign(
        month=lambda d: d["period"].dt.to_timestamp()).drop(columns="period")


def delinquency_placeholder_by_month(income: pd.DataFrame,
                                     span: pd.PeriodIndex) -> pd.DataFrame:
    """PLACEHOLDER definition only. Uses the 49 Late Fee rows as a stand-in
    until Mack defines delinquency (past-due window? value owed vs late fee
    charged?). Centralized so swapping the definition is a one-function edit."""
    late = income[income["payment_type"].eq("late_fee") & income["month"].notna()]
    g = late.groupby("month")["amount"].agg(delinquent_count="size",
                                            delinquent_value="sum")
    g = g.reindex(span, fill_value=0)
    return g.reset_index(names="period").assign(
        month=lambda d: d["period"].dt.to_timestamp()).drop(columns="period")


def _delta(series: pd.Series) -> tuple[float, float]:
    """Latest value and its change vs the prior month (for KPI cards)."""
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(fleet: pd.DataFrame, income: pd.DataFrame,
                 span: pd.PeriodIndex) -> dict:
    """As-of (latest month in span) headline numbers + month-over-month delta.
    The latest month may be partial — the page notes this."""
    owned = owned_by_month(fleet, span).set_index("month")["owned"]
    rented = rented_by_month(income, span).set_index("month")["rented"]
    avail = owned - rented
    delq = delinquency_placeholder_by_month(income, span).set_index("month")

    o, od = _delta(owned)
    r, rd = _delta(rented)
    a, ad = _delta(avail)
    dc, dcd = _delta(delq["delinquent_count"])
    dv, dvd = _delta(delq["delinquent_value"])
    return {
        "owned": (o, od),
        "rented": (r, rd),
        "available": (a, ad),
        "delinquent_count": (dc, dcd),
        "delinquent_value": (dv, dvd),
        "as_of": span.max().strftime("%b %Y"),
    }
