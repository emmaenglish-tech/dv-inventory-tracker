"""Rental reshapers over the pre-aggregated rentals tabs.

Sources (all upstream-defined):
  * ``rentals_inventory`` — owned / rented / available, precomputed for every
    instrument-cut × scope-cut (incl 'all'). ``rented`` is a distinct-customer
    count, NOT additive across cuts, so we read a cut rather than summing.
  * ``rentals_monthly``   — revenue / cost / delinquency flows, additive at
    month × instrument × high_end_rental (page filters then we sum + cumulate).
  * ``rentals_bows``      — cumulative rental-bow count (Mack's separate split).

Cut selectors: instrument ∈ {all, violin, viola, cello, unknown};
scope ∈ {all, regular, high_end}.
"""
from __future__ import annotations

import pandas as pd

RENTABLE = ("violin", "viola", "cello")


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def _cut(inv: pd.DataFrame, instrument: str, scope: str) -> pd.DataFrame:
    sub = inv[(inv["instrument"] == instrument) & (inv["scope"] == scope)]
    return sub.set_index("month").sort_index()


def inventory_for_cut(inv, span, instrument="all", scope="all") -> pd.DataFrame:
    """owned / rented / available for one precomputed cut, on the full span."""
    sub = _cut(inv, instrument, scope).reindex(span, fill_value=0)
    out = sub[["owned", "rented", "available"]].copy()
    out.index.name = "period"
    out = out.reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def inventory_by_instrument(inv, span, value, scope="all") -> pd.DataFrame:
    """One series per instrument for `value` (owned/rented/available) at `scope`.
    'unknown' is dropped for owned (not rentable) but kept for rented."""
    instrs = list(RENTABLE) if value == "owned" else [*RENTABLE, "unknown"]
    months = span.to_timestamp()
    rows = []
    for ic in instrs:
        s = _cut(inv, ic, scope).reindex(span, fill_value=0)[value]
        rows.append(pd.DataFrame({"month": months, "group": ic.title(), value: s.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def inventory_by_scope(inv, span, value, instrument="all") -> pd.DataFrame:
    """One series per scope (Regular / High-End) for `value` at `instrument`."""
    months = span.to_timestamp()
    rows = []
    for sc, label in (("regular", "Regular"), ("high_end", "High-End")):
        s = _cut(inv, instrument, sc).reindex(span, fill_value=0)[value]
        rows.append(pd.DataFrame({"month": months, "group": label, value: s.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def revenue_vs_cost_by_month(flows: pd.DataFrame, span: pd.PeriodIndex) -> pd.DataFrame:
    """`flows` already filtered to the selected instrument/scope. Sum to month,
    then cumulate (cumulatives are filter-dependent, so computed here)."""
    f = flows[flows["month"].notna()]
    rev = f.groupby("month")["revenue"].sum().reindex(span, fill_value=0.0)
    cost = f.groupby("month")["cost"].sum().reindex(span, fill_value=0.0)
    out = pd.DataFrame({"revenue": rev, "cost": cost})
    out["cum_revenue"] = out["revenue"].cumsum()
    out["cum_cost"] = out["cost"].cumsum()
    out.index.name = "period"
    out = out.reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def delinquency_by_month(flows: pd.DataFrame, span: pd.PeriodIndex) -> pd.DataFrame:
    """PLACEHOLDER — late-fee rows only. `flows` already filtered."""
    f = flows[flows["month"].notna()]
    g = (f.groupby("month")
          .agg(delinquent_count=("delinquent_count", "sum"),
               delinquent_value=("delinquent_value", "sum"))
          .reindex(span, fill_value=0))
    g.index.name = "period"
    out = g.reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def bows_owned_total(bows: pd.DataFrame) -> int:
    b = bows[bows["month"].notna()].sort_values("month")
    return int(b["bows_owned"].iloc[-1]) if len(b) else 0


def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(inv, flows, span, instrument="all", scope="all") -> dict:
    cut = inventory_for_cut(inv, span, instrument, scope).set_index("month")
    delq = delinquency_by_month(flows, span).set_index("month")
    o, od = _delta(cut["owned"])
    r, rd = _delta(cut["rented"])
    a, ad = _delta(cut["available"])
    dc, dcd = _delta(delq["delinquent_count"])
    dv, dvd = _delta(delq["delinquent_value"])
    return {
        "owned": (o, od),
        "rented": (r, rd),
        "available": (a, ad),
        "delinquent_count": (dc, dcd),
        "delinquent_value": (dv, dvd),
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }
