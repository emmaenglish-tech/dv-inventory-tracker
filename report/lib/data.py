"""Read the report tabs. This module only reads and picks rows: no sums, no grouping, no arithmetic.

Every number on screen is computed upstream in denver_violins_data (`redesign/loader/report.py`) and written
to the `rpt_*` tabs of the dv_clean Google Sheet once a day. All tabs come back in one batched API call.

Where the data comes from, in order:
  1. $DV_REPORT_DIR             a folder of rpt_*.csv files (local preview: `loader.run clean --local DIR`)
  2. st.secrets["gcp_service_account"]   Streamlit Cloud
  3. $DV_SERVICE_ACCOUNT        path to a service-account JSON key (local, against the real sheet)
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

SHEET_ID = "1dEdAr63mhBqdoRz_55QWuTfKe14GyHbhkjUW-lEq0zI"  # dv_clean (not a secret: access is Drive sharing)
SECTIONS = ("overview", "sales", "workshop", "rentals", "other", "expenses")
TABS = [f"rpt_{s}" for s in SECTIONS] + ["rpt_kpis", "rpt_headlines", "rpt_outlook", "rpt_recent_sales",
                                         "rpt_definitions", "rpt_about", "rpt_insights"]
NUMERIC = {"value", "prior", "change_pct", "sort", "baseline", "low", "high", "ttm_avg", "same_month_ly",
           "actual_to_date", "amount"}
BOOLEAN = {"partial"}
TEXT_KEEP = {"period"}  # "01".."12" must stay text
_TTL = 60 * 60  # the sheet is rebuilt once a day; re-read at most hourly


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c in NUMERIC:
            df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
        elif c in BOOLEAN:
            df[c] = df[c].astype(str).str.upper().eq("TRUE")
        else:
            df[c] = df[c].fillna("").astype(str)
    return df


def _frame(values: list[list]) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    rows = [list(r) + [""] * (len(header) - len(r)) for r in rows]
    return _typed(pd.DataFrame(rows, columns=header, dtype=object))


def _secret_account() -> dict | None:
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:  # no secrets file at all
        pass
    return None


def _from_sheet() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    import gspread
    secret = _secret_account()
    if secret is not None:
        gc = gspread.service_account_from_dict(secret)
    elif os.environ.get("DV_SERVICE_ACCOUNT"):
        gc = gspread.service_account(filename=os.environ["DV_SERVICE_ACCOUNT"])
    else:
        raise RuntimeError("No data source: set DV_REPORT_DIR (local CSVs), add gcp_service_account to "
                           "Streamlit secrets, or set DV_SERVICE_ACCOUNT to a key file.")
    book = gc.open_by_key(SHEET_ID)
    urls = {ws.title: f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={ws.id}"
            for ws in book.worksheets() if ws.title in TABS}
    present = [t for t in TABS if t in urls]  # rpt_insights only exists after its first weekly run
    got = book.values_batch_get([f"'{t}'" for t in present], params={"valueRenderOption": "UNFORMATTED_VALUE"})
    frames = {t: pd.DataFrame() for t in TABS}
    frames.update({t: _frame(r.get("values", [])) for t, r in zip(present, got["valueRanges"])})
    return frames, urls


def _from_folder(folder: str) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    frames = {}
    for t in TABS:
        path = Path(folder) / f"{t}.csv"
        blank = not path.exists() or path.stat().st_size == 0  # a missing or 0-byte file is an empty tab
        frames[t] = pd.DataFrame() if blank else _typed(pd.read_csv(path, dtype=str, keep_default_na=False))
    return frames, {}


@st.cache_data(ttl=_TTL, show_spinner="Loading the latest numbers…")
def load() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    folder = os.environ.get("DV_REPORT_DIR")
    return _from_folder(folder) if folder else _from_sheet()


# ── Row pickers (selection only) ──────────────────────────────────────────────────────────────────────
def tab(name: str) -> pd.DataFrame:
    return load()[0].get(name, pd.DataFrame())


def tab_url(name: str) -> str:
    return load()[1].get(name, f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


def basis() -> str:
    return st.session_state.get("basis") or "accrual"  # the segmented control can be cleared


def window() -> str:
    return st.session_state.get("window") or "ytd"


def chart(section: str, chart_id: str, grain: str, period: str | None = None, months: list[str] | None = None,
          basis_: str | None = None) -> pd.DataFrame:
    """Rows of one chart for the current basis, sorted by period then series order."""
    t = tab(f"rpt_{section}")
    if t.empty:
        return t
    rows = t[(t["chart"] == chart_id) & (t["basis"] == (basis_ or basis())) & (t["grain"] == grain)]
    if period is not None:
        rows = rows[rows["period"] == period]
    if months is not None:
        rows = rows[rows["period"].isin(months)]
    return rows.sort_values(["period", "sort"]).reset_index(drop=True)


def kpis(section: str, window_: str | None = None) -> pd.DataFrame:
    k = tab("rpt_kpis")
    if k.empty:
        return k
    return k[(k["section"] == section) & (k["basis"] == basis()) & (k["window"] == (window_ or window()))
             ].sort_values("sort")


def kpi(section: str, metric: str, window_: str | None = None) -> pd.Series | None:
    k = kpis(section, window_)
    hit = k[k["metric"] == metric] if not k.empty else k
    return hit.iloc[0] if len(hit) else None


def headlines(section: str) -> list[str]:
    h = tab("rpt_headlines")
    if h.empty:
        return []
    return h[(h["section"] == section) & (h["basis"] == basis())].sort_values("sort")["text"].tolist()


def insights(section: str) -> pd.DataFrame:
    """AI-written bullets for one page and the current basis (rpt_insights, written weekly upstream)."""
    i = tab("rpt_insights")
    if i.empty:
        return i
    return i[(i["section"] == section) & (i["basis"] == basis())].sort_values("sort")


def definitions(section: str) -> pd.DataFrame:
    d = tab("rpt_definitions")
    return d[d["section"] == section] if not d.empty else d


def about() -> dict[str, tuple[str, str]]:
    a = tab("rpt_about")
    return {r.key: (r.label, r.detail) for r in a.itertuples()} if not a.empty else {}


def window_labels() -> dict[str, str]:
    """window key -> its label for the current data, e.g. ytd -> 'Jan–Oct 2026'."""
    k = tab("rpt_kpis")
    if k.empty:
        return {}
    rows = k[(k["section"] == "overview") & (k["metric"] == "revenue") & (k["basis"] == "accrual")]
    return dict(zip(rows["window"], rows["window_label"]))


def prior_labels() -> dict[str, str]:
    """window key -> the same period last year, e.g. ytd -> 'Jan–Oct 2025'."""
    k = tab("rpt_kpis")
    if k.empty:
        return {}
    rows = k[(k["section"] == "overview") & (k["metric"] == "revenue") & (k["basis"] == "accrual")]
    return dict(zip(rows["window"], rows["prior_label"]))


def all_months() -> list[str]:
    """Every month in the report, oldest first (first-of-month ISO dates)."""
    rows = chart("overview", "revenue_by_area", "month", basis_="accrual")
    return sorted(rows["period"].unique().tolist()) if not rows.empty else []


def shown_months() -> list[str]:
    """The months the monthly charts show, from the sidebar span (row selection, newest last)."""
    months = all_months()
    span = st.session_state.get("span", "25")
    return months if span == "all" else months[-int(span):]
