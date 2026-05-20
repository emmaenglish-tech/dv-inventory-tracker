"""Cached loaders for the cleaned rental Google Sheets.

Design notes (the *why*, since these patterns recur across the dashboard):

* ``st.cache_resource`` vs ``st.cache_data``. The gspread *client* is a live
  connection object — not serializable, shared process-wide — so it goes in
  ``cache_resource`` (one per process). The *DataFrames* are plain data, so
  they go in ``cache_data`` with a daily TTL: a session reuses the same frame
  for every filter/interaction, and it refreshes once a day to match the
  daily ETL. This is what makes the UI feel instant.

* Auth resolves in priority order so the same code runs locally and on
  Streamlit Cloud:
    1. ``st.secrets["gcp_service_account"]``  (Cloud — paste the JSON there)
    2. ``$DV_SERVICE_ACCOUNT``                (explicit local override)
    3. ``<repo>/.config/gsperad/service_account.json``  (default checkout)

* All type coercion lives here. Pages and metric code can then trust dtypes
  (datetime, Period[M], numeric, real bools) instead of re-parsing strings.
"""

from __future__ import annotations

import os
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from gspread_dataframe import get_as_dataframe

# Cleaned-sheet coordinates (mirrors config.py in the staging repo).
FLEET_SHEET = "clean_datasets_purchases_by_product"
FLEET_TAB = "rental_fleet_df"
INCOME_SHEET = "clean_datasets_sales_by_product_cash"
INCOME_TAB = "rental_income_df"
INVENTORY_SALES_SHEET = "clean_datasets_sales_by_product_cash"
INVENTORY_SALES_TAB = "inventory_sales_df"
SERVICES_SHEET = "clean_datasets_sales_by_product_cash"
SERVICES_TAB = "services_sales_df"

# find_employee in the staging utils emits only "JF" or "EO" (everything not
# JF defaults to EO). The EO bucket therefore conflates Evan Orman (part owner /
# master bowmaker) and Eddie Miller (Mack's husband, instrument luthier). The
# Workshop page surfaces this honestly via these labels — keep them in sync with
# the staffing memory + KB 10_business_requirements §People.
EMPLOYEE_LABELS = {
    "JF": "JF",
    "EO": "Evan / Eddie (unsplit)",
}

# Consignment vs DV-Owned split — the four distribution_accounts that flow
# into inventory_sales_df partition this way upstream (instrument_sales_df.py).
_CONSIGNMENT_ACCOUNTS = frozenset({
    "Consignment Income",
    "Consignment Instrument Sales",
})

_DAILY_TTL = 60 * 60 * 24  # the ETL refreshes once a day; no point re-pulling more often

# <repo>/.config/gsperad/service_account.json — three parents up from this file
# (lib/ -> dashboard/ -> repo root). Note the intentional "gsperad" typo.
_DEFAULT_SA = Path(__file__).resolve().parents[2] / ".config" / "gsperad" / "service_account.json"

_TRUE = {"true", "1", "1.0", "yes", "y", "t"}


def _to_bool(series: pd.Series) -> pd.Series:
    """gspread returns booleans inconsistently (``True`` / ``"TRUE"`` / ``1.0``
    depending on the cell). Normalize to a real bool dtype."""
    return series.astype(str).str.strip().str.lower().isin(_TRUE)


def _secret_account() -> dict | None:
    # st.secrets raises if no secrets.toml exists at all (the normal local
    # case), so probe defensively rather than letting that escape.
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

    path = os.environ.get("DV_SERVICE_ACCOUNT") or str(_DEFAULT_SA)
    if not Path(path).is_file():
        raise FileNotFoundError(
            "No Google service account found. Either add `gcp_service_account` to "
            "Streamlit secrets (Cloud), set $DV_SERVICE_ACCOUNT to the JSON path, "
            f"or place the key at {_DEFAULT_SA}."
        )
    return gspread.service_account(filename=path)


def _read(sheet: str, tab: str) -> pd.DataFrame:
    ws = _client().open(sheet).worksheet(tab)
    df = get_as_dataframe(ws, evaluate_formulas=True)
    # gspread_dataframe pads to the grid; drop fully-empty rows/cols.
    return df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading rental fleet…")
def load_rental_fleet() -> pd.DataFrame:
    """Inventory side: one row per fleet purchase / opening / qty-adjustment.

    ``unit_count`` is uniformly 1 in the current data, but we keep it numeric
    rather than assuming, so a future multi-unit row flows through correctly.
    """
    df = _read(FLEET_SHEET, FLEET_TAB)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["transaction_date"].dt.to_period("M")
    df["unit_count"] = pd.to_numeric(df["unit_count"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["high_end_rental"] = _to_bool(df["high_end_rental"])
    # `bow` separates rental bows from rentable instruments (added to staging
    # 2026-05-19). Resilient fallback: derive it if the live sheet predates the
    # staging re-run, so the dashboard is correct either way.
    if "bow" in df.columns:
        df["bow"] = _to_bool(df["bow"])
    else:
        df["bow"] = df["search_text"].astype(str).str.contains(
            r"\bbows?\b", case=False, regex=True)
    # `accessory` excludes parts (cases, bags, fingerboards, …) from
    # rentable-instrument counts even when the memo mentions a violin/viola/
    # cello. Same resilience pattern as `bow`.
    if "accessory" in df.columns:
        df["accessory"] = _to_bool(df["accessory"])
    else:
        _acc_rx = (r"(?i)\b(violins?|violas?|cellos?|basses?)\s+"
                   r"(cases?|bags?|covers?|fingerboards?|finger\s*boards?|"
                   r"bridges?|pegs?|endpins?|tailpieces?|chin\s*rests?|"
                   r"chinrests?|shoulder\s*(?:rests?|pads?|straps?)|mutes?|"
                   r"cleaning\s*cloths?|cloths?|polish|set\s*ups?|setups?|"
                   r"straps?|stands?|strings?|rosins?)\b")
        df["accessory"] = df["memo_description"].astype(str).str.contains(
            _acc_rx, regex=True, na=False)
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading instrument sales…")
def load_inventory_sales() -> pd.DataFrame:
    """Sales side: one row per payment toward an instrument or bow sale.

    Spans four ``distribution_account`` values upstream — Instrument Sales /
    Inventory Instrument Sales / Consignment Income / Consignment Instrument
    Sales — so a single sale can be (a) one row for a paid-in-full ticket or
    (b) several rows for an installment plan. Staging adds the bookkeeping:
    ``payment_type`` ∈ {full/final payment, partial payment}, plus running
    ``total_paid`` / ``remainder_due`` per (customer, memo) group.

    Derived here:

    * ``ownership`` — "consignment" vs "dv_owned" from distribution_account,
      so the page can group without re-doing the categorical mapping.

    Cash basis only — the accrual export is collected but not yet staged
    (KB 04_sales_data_taxonomy.md). Low-tier accessory bows live in a
    different tab (``product_sales_df``) and are NOT included here; the
    Sales page calls that out.
    """
    df = _read(INVENTORY_SALES_SHEET, INVENTORY_SALES_TAB)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["transaction_date"].dt.to_period("M")
    for col in ("quantity", "sales_price", "amount", "total_paid", "remainder_due"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["bow"] = _to_bool(df["bow"])
    for col in ("distribution_account", "customer_full_name", "product_service",
                "memo_description", "brand", "maker", "details", "payment_type"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df["ownership"] = (
        df["distribution_account"].isin(_CONSIGNMENT_ACCOUNTS)
        .map({True: "consignment", False: "dv_owned"})
    )
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading workshop services…")
def load_services_sales() -> pd.DataFrame:
    """Workshop side: one row per service line item.

    Source filter (upstream): ``distribution_account in ('Services',
    'Bow Services')``. Staging (`services_sales_df.py`) adds:

    * ``service_name`` — one of 22 buckets from
      ``utils.categorize_service`` (Bow Rehair, Appraisal & Certificates,
      Sound Post Work, …; see KB ``06_utils_reference``).
    * ``employee_name`` — ``"JF"`` or ``"EO"`` from ``utils.find_employee``.
      EO is the catch-all default and bundles Evan Orman + Eddie Miller;
      a derived ``employee_label`` applies ``EMPLOYEE_LABELS`` so the UI
      doesn't have to.
    * ``instrument`` — ``_classify_instrument`` over the search text.
      ~62 % of rows are ``unknown`` (most service memos don't name the
      instrument family), so per-instrument breakdowns are noisy — the
      Workshop page prefers ``bow_flag`` for product-type splits.
    * ``bow_flag`` — already a real bool in the sheet; True for any
      bow-related service regardless of which distribution_account it
      landed in (rehairs in `Services` count too).

    The staging ``month`` column ships as a string (e.g. ``"2024-03"``);
    re-derived here from ``transaction_date`` to land as a real
    ``Period[M]`` like every other loader.

    Cash basis only — accrual export isn't staged yet
    (KB ``04_sales_data_taxonomy``).
    """
    df = _read(SERVICES_SHEET, SERVICES_TAB)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["transaction_date"].dt.to_period("M")
    for col in ("quantity", "sales_price", "amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("distribution_account", "customer_full_name", "product_service",
                "memo_description", "service_name", "employee_name"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df["instrument"] = df["instrument"].astype(str).str.strip().str.lower()
    df["bow_flag"] = _to_bool(df["bow_flag"])
    df["employee_label"] = df["employee_name"].map(EMPLOYEE_LABELS) \
                                              .fillna(df["employee_name"])
    return df


@st.cache_data(ttl=_DAILY_TTL, show_spinner="Loading rental income…")
def load_rental_income() -> pd.DataFrame:
    """Activity side: one row per fee payment.

    ``payment_type`` ∈ {rental_fee, insurance_fee, rental_deposit, late_fee};
    ``duration`` ∈ {monthly, annual, prorated, unknown}.

    Known upstream issue carried as data, not silently patched: some
    "Rental Deposit (deleted)" rows are labelled ``rental_fee`` because they
    leaked in via the Services account (see 09_known_issues). The metric layer
    excludes deposit-looking rows from the *rented* signal explicitly.
    """
    df = _read(INCOME_SHEET, INCOME_TAB)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["month"] = df["transaction_date"].dt.to_period("M")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["sales_price"] = pd.to_numeric(df["sales_price"], errors="coerce")
    for col in ("payment_type", "duration", "instrument", "product_service",
                "customer_full_name", "memo_description"):
        df[col] = df[col].astype(str).str.strip()
    df["instrument"] = df["instrument"].str.lower()
    df["high_end_rental"] = _to_bool(df["high_end_rental"])
    return df
