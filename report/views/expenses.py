import streamlit as st

from lib import charts, data, ui

ui.page_header("Expenses", "What the shop spends, split into fixed costs, variable costs and the cost of what "
                           "it sells.")
ui.headline_box("expenses")
ui.kpi_row("expenses", ["total", "fixed_per_month", "variable_per_month", "cost_of_sales"],
           inverse={"total", "fixed_per_month", "variable_per_month", "cost_of_sales"})

months, w = data.shown_months(), data.window()
now, prior = data.window_labels().get(w, ""), data.prior_labels().get(w, "")

rows = data.chart("expenses", "expenses_by_group", "month", months=months)
ui.chart_card("Spending by month", "Each column is one month. Cost of sales is mostly payouts to consignors, so it "
              "rises and falls with consignment sales.", charts.stacked_bars(rows, "expense_group"), rows,
              "expenses", "expenses_by_group", note=ui.partial_note())

rows = data.chart("expenses", "fixed_vs_variable", "month", months=months)
ui.chart_card("Fixed and variable costs", "Fixed costs (rent, insurance, salaries, software) and variable costs "
              "(supplies, card fees, contractors, shipping) each month. The gray line is the 12-month average of "
              "variable costs.", charts.lines(rows, "expense_group"), rows, "expenses", "fixed_vs_variable")

rows = data.chart("expenses", "operating_expenses_by_category", "window", period=w)
ui.chart_card("Where the money goes", f"Fixed and variable costs by category in {now} (bars); the dark tick is the "
              "same months last year. Cost of sales and non-operating costs are left out.",
              charts.ranked_bars(rows, now, prior), rows, "expenses", "operating_expenses_by_category")

st.caption("The fixed / variable split is a draft waiting for Mack's review.")
ui.definitions_box("expenses")
