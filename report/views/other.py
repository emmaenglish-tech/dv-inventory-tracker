import streamlit as st

from lib import charts, data, ui

ui.page_header("Products & other income", "Strings, cases, bow hair and other accessories, plus shipping, events "
                                          "and small miscellaneous income.")
ui.headline_box("other")
ui.kpi_row("other", ["revenue", "products", "strings", "shipping"])

months, w = data.shown_months(), data.window()
now, prior = data.window_labels().get(w, ""), data.prior_labels().get(w, "")

rows = data.chart("other", "other_by_kind", "month", months=months)
ui.chart_card("Other revenue by month", "Each column is one month, split by kind.",
              charts.stacked_bars(rows, "other_kind"), rows, "other", "other_by_kind", note=ui.partial_note())

c1, c2 = st.columns(2)
with c1:
    rows = data.chart("other", "other_by_kind", "window", period=w)
    ui.chart_card("Each kind against last year", f"{now} (blue) and the same months last year (gray).",
                  charts.this_vs_last_year(rows, now, prior), rows, "other", "other_by_kind", key="other-yoy")
with c2:
    rows = data.chart("other", "other_by_kind", "year")
    ui.chart_card("Year by year", "Each calendar year by kind. 2023 includes a one-off $132k journal entry "
                  "under Other products that is still being checked with Mack.",
                  charts.stacked_bars(rows, "other_kind", grain="year", height=360), rows, "other", "other_by_kind",
                  key="other-years")

st.caption("Insurance appraisals and certificates are counted under Workshop.")
ui.definitions_box("other")
