"""Workshop (services) metric definitions — single source of truth for the
Workshop page.

Pure functions: a (filtered) DataFrame in, a tidy DataFrame out. No Streamlit,
no I/O. Same shape as ``lib/sales`` and ``lib/rentals``.

Coverage
--------
Service line items from the clean ``services_sales_df`` tab (upstream filter:
``distribution_account in ('Services', 'Bow Services')``). Cash basis only —
accrual export isn't staged yet (KB ``04_sales_data_taxonomy``).

Definitions
-----------
Revenue        Sum of ``amount`` across service line rows — cash as received.
Transactions   Raw row count — the activity headline for services (services
               are billed per-job, so there's no "units sold" concept).
Top-N
categories     The ``service_name`` field carries 22 buckets (KB
               ``06_utils_reference §categorize_service``). The headline chart
               keeps the top-N by revenue and collapses the rest into "Other";
               the full breakdown is rendered as a side table on the page.

Employee caveat
---------------
``employee`` is ``"JF"`` or ``"EO"`` only — EO is a catch-all default that
bundles Evan Orman and Eddie Miller. Group-by-employee is honest but lossy;
the page calls this out. See KB ``10_business_requirements §People`` /
``09_known_issues §find_employee``.
"""

from __future__ import annotations

import pandas as pd

INSTRUMENTS = ("violin", "viola", "cello")


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    """Continuous month index spanning every frame — shared x-axis for charts."""
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def instruments_only(services: pd.DataFrame) -> pd.DataFrame:
    """Drop bow-services rows — mirrors lib.sales.instruments_only."""
    return services[~services["bow_flag"]]


def bows_only(services: pd.DataFrame) -> pd.DataFrame:
    return services[services["bow_flag"]]


# ── tidy helpers (same idiom as lib/sales, lib/rentals) ───────────────────
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


def _label_groups(values: pd.Series, by: str) -> pd.Series:
    if by == "bow_flag":
        return values.map({True: "Bow services", False: "Instrument services"}) \
                     .fillna("Instrument services")
    # employee_label is already human-readable in the loader; service_name
    # comes through as-is.
    return values.astype(str)


# ── metric functions ──────────────────────────────────────────────────────
def revenue_by_month(services: pd.DataFrame, span: pd.PeriodIndex,
                     by: str | None = None) -> pd.DataFrame:
    """Cash revenue per month — sum of ``amount`` on every service row."""
    s = services[services["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)["amount"].sum()
    return _tidy(grouped, span, by, "revenue")


def transactions_by_month(services: pd.DataFrame, span: pd.PeriodIndex,
                          by: str | None = None) -> pd.DataFrame:
    """Service-job count per month — the activity headline."""
    s = services[services["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False).size()
    return _tidy(grouped, span, by, "transactions")


# ── service-category collapse ─────────────────────────────────────────────
OTHER_LABEL = "Other"


def top_n_categories(services: pd.DataFrame, n: int = 6) -> list[str]:
    """The ``n`` highest-revenue ``service_name`` values in the filtered
    frame. Anything outside the top-N is intended to be collapsed into
    ``OTHER_LABEL`` for the headline chart."""
    if not len(services):
        return []
    totals = (services.groupby("service_name", dropna=False)["amount"]
                       .sum().sort_values(ascending=False))
    return list(totals.head(n).index)


def with_collapsed_category(services: pd.DataFrame, keep: list[str],
                             other_label: str = OTHER_LABEL) -> pd.DataFrame:
    """Return ``services`` with a ``category_collapsed`` column where any
    category not in ``keep`` is renamed to ``other_label``. Headline chart
    plots on this column; the full table reads ``service_name`` directly."""
    out = services.copy()
    out["category_collapsed"] = out["service_name"].where(
        out["service_name"].isin(keep), other_label)
    return out


def category_breakdown(services: pd.DataFrame) -> pd.DataFrame:
    """All-time totals per service category — the full side table.

    Columns: ``service_name``, ``revenue``, ``transactions``,
    ``revenue_share`` (fraction of total), sorted by revenue desc."""
    if not len(services):
        return pd.DataFrame(columns=["service_name", "revenue",
                                      "transactions", "revenue_share"])
    grp = (services.groupby("service_name", dropna=False)
                    .agg(revenue=("amount", "sum"),
                         transactions=("amount", "size"))
                    .reset_index()
                    .sort_values("revenue", ascending=False))
    total = grp["revenue"].sum()
    grp["revenue_share"] = grp["revenue"] / total if total else 0.0
    return grp


# ── KPI snapshot ──────────────────────────────────────────────────────────
def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(services: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """Latest-month headline numbers + month-over-month delta. The latest
    month may be partial — the page notes this."""
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
