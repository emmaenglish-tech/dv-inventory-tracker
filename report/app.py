"""Denver Violins report: a read-only view of the rpt_* tabs in the dv_clean Google Sheet.

Run locally against a folder of tabs built by the pipeline (no Google access needed):
    DV_REPORT_DIR=/path/to/local streamlit run report/app.py
"""
from __future__ import annotations

import streamlit as st

from lib import data
from lib.ui import WINDOW_NAMES

st.set_page_config(page_title="Denver Violins report", page_icon="🎻", layout="wide")

pages = st.navigation([
    st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("views/outlook.py", title="What to expect", icon=":material/trending_up:"),
    st.Page("views/sales.py", title="Instrument & bow sales", icon=":material/sell:"),
    st.Page("views/workshop.py", title="Workshop", icon=":material/build:"),
    st.Page("views/rentals.py", title="Rentals", icon=":material/key:"),
    st.Page("views/other.py", title="Products & other income", icon=":material/inventory_2:"),
    st.Page("views/expenses.py", title="Expenses", icon=":material/payments:"),
    st.Page("views/about.py", title="About the data", icon=":material/info:"),
])

# One filter row above every page; the choices persist across pages.
labels = data.window_labels()
about = data.about()
f1, f2, f3, f4 = st.columns([1.3, 1.6, 1.3, 1.4], vertical_alignment="bottom")
f1.segmented_control("Count money", ["accrual", "cash"], key="basis", default="accrual",
                     format_func={"accrual": "When invoiced", "cash": "When paid"}.get,
                     help="When invoiced (accrual): a sale counts in the month it was billed. When paid (cash): "
                          "in the month the money arrived.")
f2.selectbox("Totals for", list(WINDOW_NAMES), key="window", index=1,
             format_func=lambda w: f"{WINDOW_NAMES[w]} ({labels[w]})" if w in labels else WINDOW_NAMES[w])
f3.selectbox("Monthly charts show", ["13", "25", "all"], key="span", index=1,
             format_func={"13": "Last 12 months", "25": "Last 2 years", "all": "Since 2021"}.get)
if "as_of" in about:
    f4.markdown(f"<div style='text-align:right;color:#52514e;font-size:0.9rem;padding-bottom:0.5rem'>"
                f"Data as of <b>{about['as_of'][1]}</b></div>", unsafe_allow_html=True)
st.divider()

pages.run()
