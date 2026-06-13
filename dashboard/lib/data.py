"""Cached loaders for the pre-aggregated dashboard tabs.

The dashboard is a thin renderer now: every metric DEFINITION lives upstream in
the denver_violins_data staging pipeline, which materializes monthly rollups
into the ``clean_datasets_dashboard_aggregates`` sheet (one tab per section).
This module just loads those tabs and coerces dtypes; lib/{sales,workshop,
rentals} reshape them for the pages. Mack can open the same sheet to see the
raw aggregate numbers behind every chart — no in-memory black box.

Auth resolves in priority order so the same code runs locally and on Cloud:
  1. st.secrets["gcp_service_account"]   (Cloud)
  2. $DV_SERVICE_ACCOUNT                 (explicit local override)
  3. <repo>/.config/gsperad/service_account.json   (default checkout)
  4. ~/.config/gspread/service_account.json        (gspread's canonical default)
"""
from __future__ import annotations

import os
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from gspread_dataframe import get_as_dataframe

AGG_SHEET = "clean_datasets_dashboard_aggregates"
SALES_SHEET = "clean_datasets_sales_by_product_cash"
PURCHASES_SHEET = "clean_datasets_purchases_by_product"

_DAILY_TTL = 60 * 60 * 24  # rebuilt once a day by the ETL; no point re-pulling more often
_DEFAULT_SA = Path(__file__).resolve().parents[2] / ".config" / "gsperad" / "service_account.json"
_GSPREAD_DEFAULT_SA = Path.home() / ".config" / "gspread" / "service_account.json"
_TRUE = {"true", "1", "1.0", "yes", "y", "t"}


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(_TRUE)


def _secret_account() -> dict | None:
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


@st.cache_resource(show_spinner=False)
def _client() -> gspread.Client:
    secret = _secret_account()
    if secret is not None:
        return gspread.service_account_from_dict(secret)
    env_path = os.environ.get("DV_SERVICE_ACCOUNT")
    candidates = [Path(env_path)] if env_path else [_DEFAULT_SA, _GSPREAD_DEFAULT_SA]
    for cand in candidates:
        if cand.is_file():
            return gspread.service_account(filename=str(cand))
    raise FileNotFoundError(
        "No Google service account found. Add `gcp_service_account` to "
        "Streamlit secrets, set $DV_SERVICE_ACCOUNT, or place the key at "
        f"{_DEFAULT_SA} or {_GSPREAD_DEFAULT_SA}."
    )


def _read(tab: str) -> pd.DataFrame:
    ws = _client().open(AGG_SHEET).worksheet(tab)
    df = get_as_dataframe(ws, evaluate_formulas=True)
    return df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()


def _month_period(df: pd.DataFrame) -> pd.DataFrame:
    df["month"] = pd.to_datetime(df["month"].astype(str), errors="coerce").dt.to_period("M")
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading sales…")
def load_sales_monthly() -> pd.DataFrame:
    """month × instrument × bow × ownership → revenue, units, transactions."""
    df = _month_period(_read("sales_monthly"))
    for c in ("revenue", "units", "transactions"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["bow"] = _to_bool(df["bow"])
    df["ownership"] = df["ownership"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading workshop…")
def load_workshop_monthly() -> pd.DataFrame:
    """month × service_name × bow_flag × employee → revenue, jobs."""
    df = _month_period(_read("workshop_monthly"))
    for c in ("revenue", "jobs"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["service_name"] = df["service_name"].astype(str).str.strip()
    df["bow_flag"] = _to_bool(df["bow_flag"])
    df["employee_label"] = df["employee"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading rentals…")
def load_rentals_inventory() -> pd.DataFrame:
    """month × instrument-cut × scope-cut → owned, rented, available.

    Cuts include 'all' rollups; `rented` is a distinct-customer count that's
    NOT additive across cuts, so each cut is precomputed — select, don't sum.
    """
    df = _month_period(_read("rentals_inventory"))
    for c in ("owned", "rented", "available"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["scope"] = df["scope"].astype(str).str.strip().str.lower()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading rentals…")
def load_rentals_monthly() -> pd.DataFrame:
    """month × instrument × high_end_rental → revenue, cost, delinquent_*.

    Additive flows — sum over any instrument/scope selection and cumulate."""
    df = _month_period(_read("rentals_monthly"))
    for c in ("revenue", "cost", "delinquent_count", "delinquent_value"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["high_end_rental"] = _to_bool(df["high_end_rental"])
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading rentals…")
def load_rentals_bows() -> pd.DataFrame:
    """month → bows_owned (cumulative rental-bow count; a separate fleet category)."""
    df = _month_period(_read("rentals_bows"))
    df["bows_owned"] = pd.to_numeric(df["bows_owned"], errors="coerce")
    return df


# ── New-report tabs (materialized upstream after this lands) ──────────────────
# These loaders tolerate a missing tab so the app still runs before the upstream
# aggregator has created them — they return an empty frame with the right columns.
def _read_optional(tab: str, columns: list[str]) -> pd.DataFrame:
    try:
        return _read(tab)
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=columns)


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading product sales…")
def load_product_sales_monthly() -> pd.DataFrame:
    """month × product_category × product_subcategory → revenue, units, transactions."""
    df = _month_period(_read_optional(
        "product_sales_monthly",
        ["month", "product_category", "product_subcategory",
         "revenue", "units", "transactions"]))
    for c in ("revenue", "units", "transactions"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["product_category"] = df["product_category"].astype(str).str.strip()
    df["product_subcategory"] = df["product_subcategory"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading other income…")
def load_other_income_monthly() -> pd.DataFrame:
    """month × income_type → revenue, transactions (shipping, appraisals, COAs…)."""
    df = _month_period(_read_optional(
        "other_income_monthly",
        ["month", "income_type", "revenue", "transactions"]))
    for c in ("revenue", "transactions"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["income_type"] = df["income_type"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading expenses…")
def load_expenses_monthly() -> pd.DataFrame:
    """month × expense_category × expense_class → amount, transactions.

    `expense_class` ∈ {fixed, variable, infrequent}; `amount` is money-out
    (positive) for operating spend."""
    df = _month_period(_read_optional(
        "expenses_monthly",
        ["month", "expense_category", "expense_class", "amount", "transactions"]))
    for c in ("amount", "transactions"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["expense_category"] = df["expense_category"].astype(str).str.strip()
    df["expense_class"] = df["expense_class"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading inventory…")
def load_instrument_inventory() -> pd.DataFrame:
    """month × instrument → units (cumulative DV-owned stock), cost (cumulative)."""
    df = _month_period(_read_optional(
        "instrument_inventory_monthly",
        ["month", "instrument", "units", "cost"]))
    for c in ("units", "cost"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading inventory…")
def load_product_inventory() -> pd.DataFrame:
    """month × product_category → units (cumulative stock), cost (cumulative)."""
    df = _month_period(_read_optional(
        "product_inventory_monthly",
        ["month", "product_category", "units", "cost"]))
    for c in ("units", "cost"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["product_category"] = df["product_category"].astype(str).str.strip()
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner=False)
def global_monthly_span() -> pd.PeriodIndex:
    """Earliest month present in any monthly aggregate, extended through the
    current month. Shared bound for the cross-page date filter so the picker
    stays consistent as the user navigates between pages whose individual
    datasets cover different month ranges."""
    loaders = (
        load_sales_monthly,
        load_workshop_monthly,
        load_rentals_inventory,
        load_rentals_monthly,
        load_rentals_bows,
        load_product_sales_monthly,
        load_other_income_monthly,
        load_expenses_monthly,
        load_instrument_inventory,
        load_product_inventory,
    )
    mins: list[pd.Period] = []
    for fn in loaders:
        df = fn()
        if df is None or not len(df) or "month" not in df.columns:
            continue
        months = df["month"].dropna()
        if len(months):
            mins.append(months.min())
    if not mins:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(
        min(mins), pd.Timestamp.today().to_period("M"), freq="M")


# ── Source-data drill-down links ──────────────────────────────────────────
@st.cache_data(ttl=_DAILY_TTL, show_spinner=False)
def worksheet_url(sheet: str, tab: str) -> str | None:
    """Resolve a Google Sheets URL that opens directly to `tab` in `sheet`.
    Cached so each (sheet, tab) only round-trips once a day."""
    try:
        return _client().open(sheet).worksheet(tab).url
    except Exception:
        return None


def source_links(*sources: tuple[str, str, str]) -> None:
    """Render a 'Source — …' caption with click-through links to the clean
    Google Sheet tab(s) backing the chart above. Each source is
    ``(label, sheet, tab)``; labels distinguish multiple sources on one
    chart (e.g. Owned vs Rented in Rentals). A single source can pass an
    empty label."""
    parts: list[str] = []
    for label, sheet, tab in sources:
        url = worksheet_url(sheet, tab)
        if not url:
            continue
        link = f"[`{tab}`]({url}) ↗"
        parts.append(f"{label}: {link}" if label else link)
    if parts:
        st.caption("Source — " + " &nbsp;·&nbsp; ".join(parts))
