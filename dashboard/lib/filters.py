"""Global filters that persist across every page via ``st.session_state``.

Today this is the calendar **Date Range**. Because the aggregates are already
monthly, a day-grain range just maps to whole month periods — there is no
row-level aggregation in the app layer, so this stays cheap.

Usage on each page (after loading that page's months):

    from lib.filters import date_range_filter
    start, end = date_range_filter(all_months)        # pd.Period (month) pair
    df = df[(df["month"] >= start) & (df["month"] <= end)]
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

_KEY = "dv_date_range"  # shared session_state key → the range persists across pages


def date_range_filter(all_months: pd.PeriodIndex,
                      label: str = "Date range") -> tuple[pd.Period, pd.Period]:
    """Render the sidebar calendar range and return ``(start, end)`` as month
    Periods clamped to the data span. The selection persists across pages."""
    if all_months is None or len(all_months) == 0:
        m = pd.Timestamp.today().to_period("M")
        return m, m

    lo, hi = all_months.min(), all_months.max()
    lo_d, hi_d = lo.start_time.date(), hi.end_time.date()
    if _KEY not in st.session_state:
        st.session_state[_KEY] = (lo_d, hi_d)

    picked = st.sidebar.date_input(
        label, key=_KEY, min_value=lo_d, max_value=hi_d, format="MM/DD/YYYY",
    )

    # date_input returns a 1-tuple mid-selection (only the start chosen yet).
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        start = pd.Period(picked[0], freq="M")
        end = pd.Period(picked[1], freq="M")
    else:
        start, end = lo, hi
    return max(start, lo), min(end, hi)
