"""Sales metric definitions — single source of truth for the Sales page.

Pure functions: a (filtered) DataFrame in, a tidy DataFrame out. No Streamlit,
no I/O. Same shape as ``lib/rentals``.

Coverage
--------
Inventory sales (Instrument + Bow + Consignment) from the clean
``inventory_sales_df`` tab. Cash basis only — accrual export isn't staged
yet (KB ``04_sales_data_taxonomy``). Low-tier accessory bows live in
``product_sales_df`` and are NOT included here; the page calls that out.

Definitions
-----------
Revenue        Sum of ``amount`` across payment rows — cash as received.
Units sold     Sum of ``quantity`` on rows where ``payment_type ==
               'full/final payment'``. This avoids counting installment
               rows multiple times (a multi-payment cello sale settles
               *once* on its final payment), while still respecting batch
               quantities on single-row sales (e.g. a wholesale row with
               ``quantity=5``). ``quantity`` missing on a final-payment row
               is read as 1 (older rows that pre-date QB's quantity field).
Transactions  Raw payment-row count — surfaced as a side stat, not a headline.
"""

from __future__ import annotations

import pandas as pd

INSTRUMENTS = ("violin", "viola", "cello")
_FINAL_PAYMENT = "full/final payment"


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    """Continuous month index spanning every frame — shared x-axis for charts."""
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def instruments_only(sales: pd.DataFrame) -> pd.DataFrame:
    """Drop bow rows — the "instrument" headline excludes bows in Mack's spec."""
    return sales[~sales["bow"]]


def bows_only(sales: pd.DataFrame) -> pd.DataFrame:
    """Bow-tier rows only (from inventory_sales — accessory-tier bows in
    product_sales_df are out of scope for this MVP)."""
    return sales[sales["bow"]]


# ── tidy helpers (same idiom as lib/rentals.py) ───────────────────────────
def _tidy(grouped: pd.Series, span: pd.PeriodIndex, by: str | None,
          value_name: str, cumulative: bool = False) -> pd.DataFrame:
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
    if by == "bow":
        return values.map({True: "Bows", False: "Instruments"}).fillna("Instruments")
    if by == "ownership":
        return values.map({"consignment": "Consignment",
                            "dv_owned": "DV Owned"}).fillna(values.astype(str))
    return values.astype(str).str.title()


# ── metric functions ──────────────────────────────────────────────────────
def revenue_by_month(sales: pd.DataFrame, span: pd.PeriodIndex,
                     by: str | None = None) -> pd.DataFrame:
    """Cash revenue per month — sum of ``amount`` on every payment row."""
    s = sales[sales["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)["amount"].sum()
    return _tidy(grouped, span, by, "revenue")


def units_sold_by_month(sales: pd.DataFrame, span: pd.PeriodIndex,
                        by: str | None = None) -> pd.DataFrame:
    """Units sold per month — sum of ``quantity`` on final-payment rows.

    See module docstring for the rationale: filtering on `full/final payment`
    avoids double-counting installments while preserving batch quantities."""
    final = sales[
        (sales["payment_type"] == _FINAL_PAYMENT) & sales["month"].notna()
    ].copy()
    # Pre-2023 rows often lack `quantity`; treat the row itself as 1 unit.
    final["quantity"] = final["quantity"].fillna(1)
    keys = ["month"] + ([by] if by else [])
    grouped = final.groupby(keys, dropna=False)["quantity"].sum()
    return _tidy(grouped, span, by, "units")


def transactions_by_month(sales: pd.DataFrame, span: pd.PeriodIndex,
                          by: str | None = None) -> pd.DataFrame:
    """Payment-row count per month — useful as an activity signal (installments
    inflate this relative to ``units_sold_by_month``)."""
    s = sales[sales["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False).size()
    return _tidy(grouped, span, by, "transactions")


# ── KPI snapshot ──────────────────────────────────────────────────────────
def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(sales: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """Latest-month headline numbers + month-over-month delta. The latest
    month may be partial — the page notes this."""
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
