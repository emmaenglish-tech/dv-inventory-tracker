import streamlit as st

from lib import charts, data, ui

ui.page_header("Rentals", "Instruments on rent, rental revenue, and renters who are behind.")
ui.headline_box("rentals")
ui.kpi_row("rentals", ["active", "fleet_owned", "delinquent_customers", "delinquent_amount"],
           inverse={"delinquent_customers", "delinquent_amount"})
ui.kpi_row("rentals", ["revenue"])

months = data.shown_months()

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("rentals", "active_by_instrument", "month", months=months)
    ui.chart_card("Instruments on rent", "How many instruments were billed as rented each month, by instrument. "
                  "Numbers jump each August–September with the school year.",
                  charts.stacked_bars(rows, "instrument", money=False), rows, "rentals", "active_by_instrument",
                  money_values=False, note=ui.partial_note())
with c2:
    rows = data.chart("rentals", "rental_revenue_by_kind", "month", months=months)
    ui.chart_card("Rental revenue by month", "Monthly fees, annual fees (billed mostly in August), insurance and "
                  "the rest.", charts.stacked_bars(rows, "rental_kind"), rows, "rentals", "rental_revenue_by_kind",
                  note=ui.partial_note())

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("rentals", "delinquent_customers", "month", months=months)
    ui.chart_card("Renters behind on payments", "Renters behind at the end of each month: an invoice unpaid for "
                  "more than 30 days, autopay failing two or more months in a row, or a charge that QuickBooks "
                  "recorded but that still hadn't reached the bank 10 days later.",
                  charts.stacked_bars(rows, "delinquency", money=False), rows, "rentals", "delinquent_customers",
                  money_values=False)
with c2:
    rows = data.chart("rentals", "delinquent_amount", "month", months=months)
    ui.chart_card("Amount those renters owe", "What the late renters owed at the end of each month. Failed "
                  "autopay amounts are estimated from each renter's usual charge; charges not deposited are the "
                  "receipt amounts.",
                  charts.stacked_bars(rows, "delinquency"), rows, "rentals", "delinquent_amount")
st.caption(f"Renter names and details are in the dv_clean sheet, tab `rental_delinquency` "
           f"([open]({data.tab_url('rental_delinquency')})), which is not shown here.")

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("rentals", "rental_revenue_seasonality", "calendar_month")
    ui.chart_card("The rental year", "Rental revenue by calendar month, one line per year (darkest = this year). "
                  "Annual fees make August or September the peak.",
                  charts.lines(rows, "years", x_labels=True), rows, "rentals", "rental_revenue_seasonality")
with c2:
    rows = data.chart("rentals", "fleet_vs_rented", "month", months=months)
    ui.chart_card("Fleet and instruments on rent", "Rental instruments DV is known to have bought, and how many "
                  "were on rent. The fleet count is a floor: some early purchases have no detail and instruments "
                  "sold or retired from the fleet aren't recorded.", charts.lines(rows, "fleet", money=False), rows,
                  "rentals", "fleet_vs_rented", money_values=False)

rows = data.chart("rentals", "revenue_vs_fleet_cost", "month")
ui.chart_card("Has the fleet paid for itself?", "Running totals: rental revenue since 2021 against what DV spent on "
              "rental instruments whose purchase says what was bought (including the 2020 starting fleet). Early "
              "purchases with no detail aren't counted, so true spending is somewhat higher.",
              charts.lines(rows, "cumulative"), rows, "rentals", "revenue_vs_fleet_cost")

ui.definitions_box("rentals")
