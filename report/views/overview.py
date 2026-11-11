import streamlit as st

from lib import charts, data, ui

ui.page_header("How the shop is doing", "Revenue, costs and profit across the whole business.")
ui.headline_box("overview")
ui.kpi_row("overview", ["revenue", "expenses", "net_income"], inverse={"expenses"})
ui.kpi_row("overview", ["revenue_sales", "revenue_workshop", "revenue_rentals", "revenue_other"], caption=False)

months, w = data.shown_months(), data.window()
labels = data.window_labels()

rows = data.chart("overview", "revenue_by_area", "month", months=months)
avg = data.chart("overview", "revenue_total", "month", months=months)
avg = avg[avg["series"] == "12-month average"]
ui.chart_card(
    "Revenue by month",
    "Each column is one month, split by area. The dark line is the 12-month average up to that month, "
    "which smooths out the months that had a big instrument sale.",
    charts.stacked_bars(rows, "area", average=avg), rows, "overview", "revenue_by_area", note=ui.partial_note())

rows = data.chart("overview", "revenue_by_area", "year")
ui.chart_card("Revenue by year", "Each column is one calendar year, split by area. This year runs through the last "
              "full month.", charts.stacked_bars(rows, "area", grain="year", height=340), rows, "overview",
              "revenue_by_area", key="overview-years")

rows = data.chart("overview", "profit_bridge", "window", period=w)
ui.chart_card(
    "From revenue to profit",
    f"{labels.get(w, '')}: start with revenue, take away each kind of cost, and see what's left. Red bars are "
    "costs, blue bars add money, and gray bars are running totals.",
    charts.waterfall(rows, {"Revenue", "Gross profit", "Operating profit", "Net income"}),
    rows, "overview", "profit_bridge")

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("overview", "revenue_by_area", "window", period=w)
    now, prior = labels.get(w, ""), data.prior_labels().get(w, "")
    ui.chart_card("Each area against last year", f"Revenue for {now} (blue) and the same months last year (gray).",
                  charts.this_vs_last_year(rows, now, prior, height=340), rows, "overview", "revenue_by_area",
                  key="overview-yoy")
with c2:
    rows = data.chart("overview", "net_income", "year")
    ui.chart_card("Year by year", "Revenue, all expenses and net income for each calendar year. This year runs "
                  "through the last full month.", charts.grouped_bars(rows, "money"), rows, "overview",
                  "net_income")

ui.kpi_row("overview", ["instrument_liabilities"])
rows = data.chart("overview", "instrument_liabilities", "month", months=months)
ui.chart_card("Instrument liabilities", "Money DV holds that belongs to someone else, at the end of each month: "
              "rental deposits, deposits on instrument sales, and money a consignor placed with DV to buy "
              "instruments. Loans from investors aren't included.",
              charts.stacked_bars(rows, "liability"), rows, "overview", "instrument_liabilities",
              note=ui.partial_note())

ui.definitions_box("overview")
