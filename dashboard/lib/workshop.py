"""Workshop reshapers over the pre-aggregated ``workshop_monthly`` tab.

Definitions live upstream; these group/sum the materialized rollup. Same
page-facing API as before. ``jobs`` (the upstream measure) is surfaced as
``transactions`` so the page code is unchanged.
"""
from __future__ import annotations

import pandas as pd

INSTRUMENTS = ("violin", "viola", "cello")
OTHER_LABEL = "Other"


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def instruments_only(services: pd.DataFrame) -> pd.DataFrame:
    return services[~services["bow_flag"]]


def bows_only(services: pd.DataFrame) -> pd.DataFrame:
    return services[services["bow_flag"]]


def _label_groups(values: pd.Series, by: str) -> pd.Series:
    if by == "bow_flag":
        return values.map({True: "Bow services", False: "Instrument services"}) \
                     .fillna("Instrument services")
    return values.astype(str)


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


def revenue_by_month(services, span, by=None):
    s = services[services["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)["revenue"].sum()
    return _tidy(grouped, span, by, "revenue")


def transactions_by_month(services, span, by=None):
    s = services[services["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)["jobs"].sum()
    return _tidy(grouped, span, by, "transactions")


def top_n_categories(services: pd.DataFrame, n: int = 6) -> list[str]:
    if not len(services):
        return []
    totals = (services.groupby("service_name", dropna=False)["revenue"]
                       .sum().sort_values(ascending=False))
    return list(totals.head(n).index)


def with_collapsed_category(services, keep, other_label=OTHER_LABEL):
    out = services.copy()
    out["category_collapsed"] = out["service_name"].where(
        out["service_name"].isin(keep), other_label)
    return out


def category_breakdown(services: pd.DataFrame) -> pd.DataFrame:
    if not len(services):
        return pd.DataFrame(columns=["service_name", "revenue",
                                     "transactions", "revenue_share"])
    grp = (services.groupby("service_name", dropna=False)
                    .agg(revenue=("revenue", "sum"), transactions=("jobs", "sum"))
                    .reset_index()
                    .sort_values("revenue", ascending=False))
    total = grp["revenue"].sum()
    grp["revenue_share"] = grp["revenue"] / total if total else 0.0
    return grp


def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(services: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    rev = revenue_by_month(services, span).set_index("month")["revenue"]
    txn = transactions_by_month(services, span).set_index("month")["transactions"]
    r, rd = _delta(rev)
    t, td = _delta(txn)
    return {
        "revenue": (r, rd),
        "transactions": (t, td),
        "all_time_revenue": float(rev.sum()),
        "all_time_transactions": float(txn.sum()),
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }
