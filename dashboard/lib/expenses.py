"""Expense reshapers over the pre-aggregated ``expenses_monthly`` tab.

Source (upstream-defined): amount / transactions at
month × expense_category × expense_class, where
``expense_class`` ∈ {fixed, variable, infrequent} (lowercase) and ``amount`` is
money-out (positive) for operating spend. Additive flows — sum freely.

**Owner draws / equity are NOT expenses.** ``expenses_monthly`` may carry
``owner_draw`` / ``owner_equity`` categories whose amounts are negative by
convention (equity movements, not operating costs). They'd distort every
expense total and the fixed/variable/infrequent split, so ``operating_only``
drops them and the page totals on that. ``OWNER_CATEGORIES`` lists them in one
place; if upstream renames them, update here.

Pure functions, no I/O — mirrors lib/{sales,workshop} so the page is thin.
"""
from __future__ import annotations

import pandas as pd

# Equity movements booked into the expense feed — excluded from expense totals.
# Matched case-insensitively against ``expense_category``.
OWNER_CATEGORIES = ("owner_draw", "owner_equity")

# Lowercase data → Title-case display, in fixed → variable → infrequent order.
CLASS_ORDER = ["fixed", "variable", "infrequent"]
CLASS_LABELS = {"fixed": "Fixed", "variable": "Variable",
                "infrequent": "Infrequent"}


def monthly_span(*frames: pd.DataFrame) -> pd.PeriodIndex:
    parts = [f["month"].dropna() for f in frames if len(f)]
    if not parts:
        return pd.PeriodIndex([], freq="M")
    months = pd.concat(parts)
    if months.empty:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(months.min(), months.max(), freq="M")


def operating_only(expenses: pd.DataFrame) -> pd.DataFrame:
    """Drop owner draw / equity rows so totals are operating spend only."""
    cat = expenses["expense_category"].astype(str).str.strip().str.lower()
    return expenses[~cat.isin(OWNER_CATEGORIES)]


def class_label(values: pd.Series) -> pd.Series:
    """lowercase expense_class → Title-case label (unknown values pass through
    title-cased so nothing silently drops)."""
    lower = values.astype(str).str.strip().str.lower()
    return lower.map(CLASS_LABELS).fillna(lower.str.title())


def _tidy(grouped: pd.Series, span: pd.PeriodIndex, by: str | None,
          value_name: str) -> pd.DataFrame:
    if by:
        wide = grouped.unstack(by, fill_value=0).reindex(span, fill_value=0)
        out = wide.reset_index(names="period").melt(
            id_vars="period", var_name="group", value_name=value_name)
        if by == "expense_class":
            out["group"] = class_label(out["group"])
        else:
            out["group"] = out["group"].astype(str)
    else:
        ser = grouped.reindex(span, fill_value=0)
        ser.index.name = "period"
        out = ser.rename(value_name).reset_index()
    out["month"] = out["period"].dt.to_timestamp()
    return out.drop(columns="period")


def _by_month(expenses: pd.DataFrame, span: pd.PeriodIndex, by: str | None,
              measure: str) -> pd.DataFrame:
    s = expenses[expenses["month"].notna()]
    keys = ["month"] + ([by] if by else [])
    grouped = s.groupby(keys, dropna=False)[measure].sum()
    return _tidy(grouped, span, by, measure)


def amount_by_month(expenses, span, by=None):
    return _by_month(expenses, span, by, "amount")


def transactions_by_month(expenses, span, by=None):
    return _by_month(expenses, span, by, "transactions")


def category_breakdown(expenses: pd.DataFrame) -> pd.DataFrame:
    """Amount / transactions per (category, class), amount desc. The class is
    Title-cased for display. Empty-safe."""
    cols = ["expense_category", "expense_class", "amount", "transactions",
            "amount_share"]
    if not len(expenses):
        return pd.DataFrame(columns=cols)
    grp = (expenses.groupby(["expense_category", "expense_class"],
                            dropna=False)
                   .agg(amount=("amount", "sum"),
                        transactions=("transactions", "sum"))
                   .reset_index()
                   .sort_values("amount", ascending=False))
    grp["expense_class"] = class_label(grp["expense_class"])
    total = grp["amount"].sum()
    grp["amount_share"] = grp["amount"] / total if total else 0.0
    return grp[cols]


def _delta(series: pd.Series) -> tuple[float, float]:
    if len(series) == 0:
        return 0.0, 0.0
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else 0.0
    return latest, latest - prev


def kpi_snapshot(expenses: pd.DataFrame, span: pd.PeriodIndex) -> dict:
    """Total over the selected range + one total per expense_class (BANs reflect
    the date range). ``expenses`` should already be operating-only. ``by_class``
    is an ordered (Fixed, Variable, Infrequent) list of (label, total)."""
    amt = amount_by_month(expenses, span).set_index("month")["amount"]
    a, ad = _delta(amt)

    by_class = []
    if len(expenses):
        cls_tot = (expenses.assign(_c=class_label(expenses["expense_class"]))
                           .groupby("_c")["amount"].sum())
    else:
        cls_tot = pd.Series(dtype=float)
    for key in CLASS_ORDER:
        label = CLASS_LABELS[key]
        by_class.append((label, float(cls_tot.get(label, 0.0))))

    return {
        "total_amount": float(amt.sum()),
        "latest_amount": (a, ad),
        "by_class": by_class,
        "as_of": span.max().strftime("%b %Y") if len(span) else "—",
    }
