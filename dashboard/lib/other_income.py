"""Other-income reshapers over the pre-aggregated ``other_income_monthly`` tab.

Source (upstream-defined): revenue / transactions at month × income_type.
Additive flows — sum over any income_type selection and over months. Today this
is mostly shipping income; appraisals / COAs slot in as new income_types once
they're tagged upstream, with no page change needed.

Pure functions, no I/O — mirrors lib/{sales,workshop} so the page is thin.
"""
from __future__ import annotations

import pandas as pd


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def _tidy(grouped: pd.Series, span: pd.PeriodIndex, by: str | None,
          value_name: str) -> pd.DataFrame:
    if by:
        wide = grouped.unstack(by, fill_value=0).reindex(span, fill_value=0)
        out = wide.reset_index(names="period").melt(
            id_vars="period", var_name="group", value_name=value_name)
        out["group"] = out["group"].astype(str)
    else:
        ser = grouped.reindex(span, fill_value=0)
        ser.index.name = "period"
        out = ser.rename(value_name).reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def _by_month(income: pd.DataFrame, span: pd.PeriodIndex, by: str | None,
              measure: str) -> pd.DataFrame:
    s = income[income["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)[measure].sum()
    return _tidy(grouped, span, by, measure)


def revenue_by_month(income, span, by=None):
    return _by_month(income, span, by, "revenue")


def transactions_by_month(income, span, by=None):
    return _by_month(income, span, by, "transactions")


def income_types(income: pd.DataFrame) -> list[str]:
    """Income types present, ordered by total revenue (desc)."""
    if not len(income):
        return []
    totals = (income.groupby("income_type", dropna=False)["revenue"]
                    .sum().sort_values(ascending=False))
    return list(totals.index.astype(str))


def type_breakdown(income: pd.DataFrame) -> pd.DataFrame:
    """Revenue / transactions per income_type, revenue desc. Empty-safe."""
    cols = ["income_type", "revenue", "transactions", "revenue_share"]
    if not len(income):
        return pd.DataFrame(columns=cols)
    grp = (income.groupby("income_type", dropna=False)
                 .agg(revenue=("revenue", "sum"),
                      transactions=("transactions", "sum"))
                 .reset_index()
                 .sort_values("revenue", ascending=False))
    total = grp["revenue"].sum()
    grp["revenue_share"] = grp["revenue"] / total if total else 0.0
    return grp[cols]


def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(income: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """Total over the selected range + per-income_type totals (BANs reflect the
    date range). ``by_type`` is an ordered list of (label, total) for the cards.
    """
    rev = revenue_by_month(income, span).set_index("month")["revenue"]
    r, rd = _delta(rev)
    bd = type_breakdown(income)
    by_type = [(row["income_type"], float(row["revenue"]))
               for _, row in bd.iterrows()]
    return {
        "total_revenue": float(rev.sum()),
        "latest_revenue": (r, rd),
        "by_type": by_type,
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }
