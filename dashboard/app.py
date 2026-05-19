"""Denver Violins — dashboard entrypoint.

Streamlit auto-discovers everything in ``pages/`` for the nav. This file is
the landing page: project framing, data freshness, and pointers to the
section pages as they come online.
"""

import streamlit as st

from lib.data import load_rental_fleet, load_rental_income
from lib.theme import apply_theme

st.set_page_config(page_title="Denver Violins", page_icon="🎻", layout="wide")
apply_theme()

st.title("Denver Violins")
st.caption("Operational dashboard for Mack — sales, rentals, workshop, "
           "expenses. Data refreshes daily from QuickBooks.")

# Freshness — cheap probes via the cached loaders.
fleet = load_rental_fleet()
income = load_rental_income()

c1, c2, c3 = st.columns(3)
c1.metric("Fleet ledger rows", f"{len(fleet):,}",
          help="clean_datasets_purchases_by_product / rental_fleet_df")
c2.metric("Rental income rows", f"{len(income):,}",
          help="clean_datasets_sales_by_product_cash / rental_income_df")
c3.metric("Most recent income month",
          str(income["month"].dropna().max()))

st.markdown("### Sections")
st.markdown(
    "- **Rentals** — Mack's five headline metrics, revenue vs fleet cost, "
    "delinquency placeholder. *(Available now — use the nav on the left.)*\n"
    "- **Sales** — instrument / bow / product sales by month, cash vs accrual. "
    "*(Coming next.)*\n"
    "- **Workshop** — services by contractor / owner. *(Planned.)*\n"
    "- **Expenses** — by category, fixed vs variable. *(Planned.)*\n"
)
