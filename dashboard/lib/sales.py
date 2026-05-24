"""Sales reshapers over the pre-aggregated ``sales_monthly`` tab.

Definitions now live upstream (denver_violins_data); the page hands us a
filtered slice of the materialized rollup and these functions just group/sum
the pre-computed measures. Pure functions, no I/O — same page-facing API as
before, so the page barely changed.
"""
from __future__ import annotations

import pandas as pd

INSTRUMENTS = ("violin", "viola", "cello")


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def instruments_only(sales: pd.DataFrame) -> pd.DataFrame:
    return sales[~sales["bow"]]


def bows_only(sales: pd.DataFrame) -> pd.DataFrame:
    return sales[sales["bow"]]


def _label_groups(values: pd.Series, by: str) -> pd.Series:
    if by == "bow":
        return values.map({True: "Bows", False: "Instruments"}).fillna("Instruments")
    if by == "ownership":
        return values.map({"consignment": "Consignment",
                           "dv_owned": "DV Owned"}).fillna(values.astype(str))
    return values.astype(str).str.title()


def _tidy(grouped: pd.Series, span: pd.PeriodIndex, by: str | None,
          value_name: str) -> pd.DataFrame:
    if by:
        wide = grouped.unstack(by, fill_value=0).reindex(span, fill_value=0)
        out = wide.reset_index(names="period").melt(
            id_vars="period", var_name="group", value_name=value_name)
        out["group"] = _label_groups(out["group"], by)
    else:
        ser = grouped.reindex(span, fill_value=0)
        ser.index.name = "period"
        out = ser.rename(value_name).reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def _by_month(sales: pd.DataFrame, span: pd.PeriodIndex, by: str | None,
              measure: str) -> pd.DataFrame:
    s = sales[sales["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)[measure].sum()
    return _tidy(grouped, span, by, measure)


def revenue_by_month(sales, span, by=None):
    return _by_month(sales, span, by, "revenue")


def units_sold_by_month(sales, span, by=None):
    return _by_month(sales, span, by, "units")


def transactions_by_month(sales, span, by=None):
    return _by_month(sales, span, by, "transactions")


def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(sales: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    rev = revenue_by_month(sales, span).set_index("month")["revenue"]
    units = units_sold_by_month(sales, span).set_index("month")["units"]
    txn = transactions_by_month(sales, span).set_index("month")["transactions"]
    r, rd = _delta(rev)
    u, ud = _delta(units)
    t, td = _delta(txn)
    return {
        "revenue": (r, rd),
        "units": (u, ud),
        "transactions": (t, td),
        "all_time_revenue": float(rev.sum()),
        "all_time_units": float(units.sum()),
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }
