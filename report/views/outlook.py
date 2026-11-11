import pandas as pd
import streamlit as st

from lib import charts, data, ui

ui.page_header("What to expect", "How much revenue a typical month brings, by area, and how far real months "
                                 "usually stray from it.")
ui.headline_box("outlook")

look = data.tab("rpt_outlook")
look = look[look["basis"] == data.basis()] if not look.empty else look
AREAS = ["Total", "Workshop", "Rentals", "Other", "Sales", "Sales: Under $10k", "Sales: $10k–$50k",
         "Sales: $50k and up"]

if look.empty:
    st.info("No outlook yet.")
    st.stop()

month = look[look["horizon"] == "month"]
current = month["target_month"].min()
this = month[month["target_month"] == current].set_index("area")
year = look[look["horizon"] == "next_12_months"].set_index("area")

with st.container(border=True):
    st.markdown(f"**This month ({this['target_label'].iloc[0]}) and the next 12 months**")
    st.caption("A typical month is the average of the last 12 full months (Rentals also follows its season). "
               "The usual range covers 8 of every 10 months over the last two years.")
    table = pd.DataFrame({
        "Area": AREAS,
        "Typical month": [this.at[a, "baseline"] for a in AREAS],
        "Usual range": [f"{ui.money(this.at[a, 'low'])} – {ui.money(this.at[a, 'high'])}" for a in AREAS],
        "Same month last year": [this.at[a, "same_month_ly"] for a in AREAS],
        "So far this month": [this.at[a, "actual_to_date"] for a in AREAS],
        "Next 12 months": [year.at[a, "baseline"] for a in AREAS],
        "Next 12 months, usual range": [f"{ui.money(year.at[a, 'low'])} – {ui.money(year.at[a, 'high'])}"
                                        for a in AREAS],
    })
    money_cols = ["Typical month", "Same month last year", "So far this month", "Next 12 months"]
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="dollar") for c in money_cols})
    st.caption("Sales is split by the size of each sale. Sales of \\$50k and up happen a few times a year, so their "
               "typical month is a share of a yearly total, not something to expect every month.")

HISTORY = {"Total": ("overview", "revenue_total", "Revenue"), "Sales": ("overview", "revenue_by_area", "Sales"),
           "Workshop": ("overview", "revenue_by_area", "Workshop"),
           "Rentals": ("overview", "revenue_by_area", "Rentals"), "Other": ("overview", "revenue_by_area", "Other"),
           "Sales: Under $10k": ("sales", "sales_by_size", "Under $10k"),
           "Sales: $10k–$50k": ("sales", "sales_by_size", "$10k–$50k"),
           "Sales: $50k and up": ("sales", "sales_by_size", "$50k and up")}

st.markdown("#### The last two years and the year ahead")
st.caption("The dark line is what actually came in each month. The blue line is a typical month and the shaded "
           "band the usual range. A month outside the band is unusual, not necessarily a problem.")
for pair in (("Workshop", "Rentals"), ("Other", "Sales")):
    for col, area in zip(st.columns(2), pair):
        with col, st.container(border=True):
            st.markdown(f"**{area}**")
            section, chart_id, series = HISTORY[area]
            hist = data.chart(section, chart_id, "month", months=data.all_months()[-25:-1])
            hist = hist[hist["series"] == series]
            ahead = month[month["area"] == area].sort_values("target_month")
            st.plotly_chart(charts.outlook_band(hist, ahead, height=300), width="stretch", config=charts.config(),
                            key=f"outlook-{area}")
            with st.expander("Show the numbers"):
                st.dataframe(ahead[["target_label", "baseline", "low", "high", "same_month_ly"]].rename(columns={
                    "target_label": "Month", "baseline": "Typical month", "low": "Low end", "high": "High end",
                    "same_month_ly": "Same month last year"}), hide_index=True, width="stretch",
                    column_config={c: st.column_config.NumberColumn(format="dollar")
                                   for c in ("Typical month", "Low end", "High end", "Same month last year")})
                st.caption(f"Source: [dv_clean › rpt_outlook]({data.tab_url('rpt_outlook')}).")

ui.kpi_row("sales", ["major_sales"], window="ytd")
ui.definitions_box("outlook")
