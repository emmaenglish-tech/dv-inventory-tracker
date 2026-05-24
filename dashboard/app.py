"""Denver Violins — dashboard entrypoint.

Streamlit auto-discovers everything in ``pages/`` for the nav. This file is
the landing page: project framing, data freshness, and pointers to the
section pages. Everything reads the pre-aggregated
``clean_datasets_dashboard_aggregates`` sheet (built daily upstream).
"""

import streamlit as st

from lib.data import (load_rentals_inventory, load_rentals_monthly,
                      load_sales_monthly, load_workshop_monthly)
from lib.theme import apply_theme

st.set_page_config(page_title="Denver Violins", page_icon="🎻", layout="wide")
apply_theme()

st.title("Denver Violins")
st.caption("Operational dashboard for Mack — sales, rentals, workshop, "
           "expenses. Reads the daily aggregate sheet (rebuilt from QuickBooks "
           "by the ETL); open that sheet to drill into the raw numbers.")

# Freshness — cheap probes via the cached loaders (the aggregate sheet).
sales = load_sales_monthly()
workshop = load_workshop_monthly()
inv = load_rentals_inventory()
flows = load_rentals_monthly()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sales agg rows", f"{len(sales):,}",
          help="clean_datasets_dashboard_aggregates / sales_monthly")
c2.metric("Workshop agg rows", f"{len(workshop):,}",
          help="clean_datasets_dashboard_aggregates / workshop_monthly")
c3.metric("Rentals flow rows", f"{len(flows):,}",
          help="clean_datasets_dashboard_aggregates / rentals_monthly")
c4.metric("Most recent sales month",
          str(sales["month"].dropna().max()))

st.markdown("### Sections")
st.markdown(
    "- **Rentals** — Mack's five headline metrics, revenue vs fleet cost, "
    "delinquency placeholder. *(Available now — use the nav on the left.)*\n"
    "- **Sales** — instrument / bow revenue and units, consignment vs DV-Owned, "
    "Wholesale/Auction placeholder. Cash basis. "
    "*(Available now — use the nav on the left.)*\n"
    "- **Workshop** — services revenue + jobs by category, instrument vs bow, "
    "and employee (JF vs EO/Evan Orman — Eddie's work currently lumped in). "
    "Cash basis. "
    "*(Available now — use the nav on the left.)*\n"
    "- **Expenses** — by category, fixed vs variable. *(Planned.)*\n"
)

st.caption("Numbers come from the aggregate sheet, which Mack can open directly "
           "to see the raw monthly rollups behind every chart.")
