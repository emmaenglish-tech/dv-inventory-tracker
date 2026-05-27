"""Product reshapers over two pre-aggregated tabs.

Two sources, both upstream-defined:
  * ``product_sales_monthly`` — revenue / units / transactions at
    month × product_category × product_subcategory. Additive flows: sum over
    any category selection.
  * ``product_inventory_monthly`` — units / cost at month × product_category.
    Cumulative stock levels, NOT flows — read the latest month in range for an
    "as of today" snapshot; don't sum across months.

Pure functions, no I/O — same shape as lib/{sales,workshop,rentals} so the page
is a thin renderer. "Products" = the accessory line (rosin, cases, strings,
accessory bows…); instrument/bow sales live on the Sales page.
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


# ── Product sales (additive flows) ────────────────────────────────────────────
def _sales_by_month(sales: pd.DataFrame, span: pd.PeriodIndex, by: str | None,
                    measure: str) -> pd.DataFrame:
    s = sales[sales["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)[measure].sum()
    return _tidy(grouped, span, by, measure)


def revenue_by_month(sales, span, by=None):
    return _sales_by_month(sales, span, by, "revenue")


def units_by_month(sales, span, by=None):
    return _sales_by_month(sales, span, by, "units")


def transactions_by_month(sales, span, by=None):
    return _sales_by_month(sales, span, by, "transactions")


def category_breakdown(sales: pd.DataFrame) -> pd.DataFrame:
    """Revenue / units / transactions per (category, subcategory), revenue desc.

    Empty-safe: returns a correctly-columned empty frame when there are no rows.
    """
    cols = ["product_category", "product_subcategory", "revenue", "units",
            "transactions", "revenue_share"]
    if not len(sales):
        return pd.DataFrame(columns=cols)
    grp = (sales.groupby(["product_category", "product_subcategory"],
                         dropna=False)
                .agg(revenue=("revenue", "sum"), units=("units", "sum"),
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


def sales_kpis(sales: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """Totals over the selected range (BANs reflect the date range, not a
    single month) plus a month-over-month delta on the latest month."""
    rev = revenue_by_month(sales, span).set_index("month")["revenue"]
    units = units_by_month(sales, span).set_index("month")["units"]
    r, rd = _delta(rev)
    u, ud = _delta(units)
    return {
        "total_revenue": float(rev.sum()),
        "total_units": float(units.sum()),
        "latest_revenue": (r, rd),
        "latest_units": (u, ud),
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }


# ── Product inventory (cumulative stock — "as of" the latest month) ───────────
def inventory_by_month(inv: pd.DataFrame, span: pd.PeriodIndex,
                       by: str | None = None) -> pd.DataFrame:
    """units + cost over the span. Stock is a level, not a flow, so each month
    holds the standing total; we sum within a month across the `by` dimension
    but never across months."""
    i = inv[inv["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    units = i.groupby(keys, dropna=False)["units"].sum()
    cost = i.groupby(keys, dropna=False)["cost"].sum()
    u = _tidy(units, span, by, "units")
    c = _tidy(cost, span, by, "cost")
    merge_on = ["month"] + (["group"] if by else [])
    return u.merge(c, on=merge_on, how="outer")


def inventory_snapshot(inv: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """As-of-today snapshot = the latest month in range. Totals are the standing
    stock that month, not a sum across months. Delta vs the prior month."""
    by_m = inventory_by_month(inv, span)
    by_m = by_m.set_index("month").sort_index()
    u, ud = _delta(by_m["units"]) if len(by_m) else (0.0, 0.0)
    c, cd = _delta(by_m["cost"]) if len(by_m) else (0.0, 0.0)
    return {
        "units": (u, ud),
        "cost": (c, cd),
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }


def inventory_breakdown(inv: pd.DataFrame, span: pd.PeriodIndex) -> pd.DataFrame:
    """Per-category standing stock as of the latest month in range."""
    cols = ["product_category", "units", "cost"]
    if not len(inv) or not len(span):
        return pd.DataFrame(columns=cols)
    latest = span.max()
    snap = inv[inv["month"] == latest]
    if not len(snap):
        return pd.DataFrame(columns=cols)
    grp = (snap.groupby("product_category", dropna=False)
               .agg(units=("units", "sum"), cost=("cost", "sum"))
               .reset_index()
               .sort_values("cost", ascending=False))
    return grp[cols]
