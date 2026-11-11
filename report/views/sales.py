import streamlit as st

from lib import charts, data, ui

ui.page_header("Instrument & bow sales", "Violins, violas, cellos, basses and bows: what sold, on whose behalf, "
                                         "and what DV keeps.")
ui.headline_box("sales")
ui.kpi_row("sales", ["revenue", "units", "avg_sale"], caption=False)
ui.kpi_row("sales", ["consignment_share", "dv_keeps", "major_sales"])

months, w = data.shown_months(), data.window()
now, prior = data.window_labels().get(w, ""), data.prior_labels().get(w, "")

rows = data.chart("sales", "sales_by_instrument", "month", months=months)
ui.chart_card("Sales by month, by instrument",
              "Each column is one month. A few big sales decide most months, so compare quarters or years rather "
              "than single months.", charts.stacked_bars(rows, "instrument"), rows, "sales", "sales_by_instrument",
              note=ui.partial_note())

rows = data.chart("sales", "units_by_instrument", "month", months=months)
ui.chart_card("Instruments & bows sold by month",
              "How many sold each month, by instrument. A deposit and the installments for one instrument count "
              "once, in the month of the first payment.", charts.stacked_bars(rows, "instrument", money=False),
              rows, "sales", "units_by_instrument", note=ui.partial_note(), money_values=False, key="units-month")

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("sales", "sales_by_instrument", "window", period=w)
    ui.chart_card("Each instrument against last year", f"Sales for {now} (blue) and the same months last year "
                  "(gray).", charts.this_vs_last_year(rows, now, prior), rows, "sales", "sales_by_instrument",
                  key="sales-yoy")
with c2:
    rows = data.chart("sales", "units_by_instrument", "window", period=w)
    ui.chart_card("Instruments & bows sold", f"How many sold in {now} (blue) and the same months last year "
                  "(gray). Deposits and installments of one instrument count once.",
                  charts.this_vs_last_year(rows, now, prior, money=False), rows, "sales", "units_by_instrument",
                  money_values=False, key="units-yoy")

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("sales", "sales_by_ownership", "year")
    ui.chart_card("Consignment, DV-owned and made in-house",
                  "Sales each year by who owned the instrument. This year runs through the last full month.",
                  charts.stacked_bars(rows, "ownership", grain="year", height=340), rows, "sales",
                  "sales_by_ownership")
with c2:
    rows = data.chart("sales", "sales_by_size", "year")
    ui.chart_card("Sales by size", "Each year's sales split by the size of the sale. The darkest part, sales of "
                  "$50k and up, is the least predictable.", charts.stacked_bars(rows, "size", grain="year",
                                                                               height=340),
                  rows, "sales", "sales_by_size")

rows = data.chart("sales", "consignment_kept_12m", "month", months=months)
ui.chart_card("What DV keeps from consignment (rolling 12 months)",
              "Consignment sales, what was paid out to consignors and makers, and the difference DV keeps. Each "
              "point covers the 12 months up to that month, because payouts often land a month or more after "
              "the sale.", charts.lines(rows, "consignment"), rows, "sales", "consignment_kept_12m")

recent = data.tab("rpt_recent_sales")
with st.container(border=True):
    st.markdown("**What sold recently**")
    st.caption("Every instrument and bow sale line in the last full month and this month so far, newest first "
               "(always counted when invoiced). Installments and deposits appear as their own lines.")
    if recent.empty:
        st.info("No sales in this period.")
    else:
        st.dataframe(recent.rename(columns={
            "period_label": "Month", "txn_date": "Date", "description": "What sold", "instrument": "Instrument",
            "ownership": "Owned by", "amount": "Amount"}),
            hide_index=True, width="stretch",
            column_config={"Amount": st.column_config.NumberColumn(format="dollar")})
    st.caption(f"Source: [dv_clean › rpt_recent_sales]({data.tab_url('rpt_recent_sales')}).")

st.caption("Not shown yet: wholesale vs auction for DV-owned stock (QuickBooks doesn't link a sale to how the "
           "instrument was bought).")
ui.definitions_box("sales")
