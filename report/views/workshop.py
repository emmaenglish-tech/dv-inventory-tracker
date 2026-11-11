import streamlit as st

from lib import charts, data, ui

ui.page_header("Workshop", "Repairs, rehairs, setups and appraisals on instruments and bows.")
ui.headline_box("workshop")
ui.kpi_row("workshop", ["revenue", "jobs", "avg_job", "bow_share"])

months, w = data.shown_months(), data.window()
now, prior = data.window_labels().get(w, ""), data.prior_labels().get(w, "")

rows = data.chart("workshop", "workshop_by_kind", "month", months=months)
ui.chart_card("Workshop revenue by month", "Each column is one month, split into instrument repairs, bow rehairs, "
              "other bow repairs and appraisals.", charts.stacked_bars(rows, "workshop_kind"), rows, "workshop",
              "workshop_by_kind", note=ui.partial_note())

rows = data.chart("workshop", "workshop_by_kind", "window", period=w)
ui.chart_card("Instrument and bow work against last year",
              f"Revenue for {now} (blue) and the same months last year (gray), by kind of work.",
              charts.this_vs_last_year(rows, now, prior), rows, "workshop", "workshop_by_kind", key="workshop-yoy")

c1, c2 = st.columns([3, 2])
with c1:
    rows = data.chart("workshop", "workshop_by_service", "window", period=w)
    ui.chart_card("Kinds of work", f"Revenue by kind of work in {now} (bars); the dark tick is the same months "
                  "last year. Read from each line's item and description.",
                  charts.ranked_bars(rows, now, prior), rows, "workshop", "workshop_by_service")
with c2:
    rows = data.chart("workshop", "workshop_jobs", "window", period=w)
    ui.chart_card("Jobs", f"How many jobs in {now} (blue) and the same months last year (gray). Each invoice "
                  "line is one job.", charts.this_vs_last_year(rows, now, prior, money=False), rows, "workshop",
                  "workshop_jobs", money_values=False)

rows = data.chart("workshop", "workshop_by_worker", "year")
ui.chart_card("Who did the work", "Revenue each year by who did the work. Only Jesse's (JF) work is tagged in "
              "QuickBooks; the rest is assumed to be Evan's (bows) or Eddy's (instruments), so their numbers also "
              "include work by Eben, Tim and Sebastian.",
              charts.stacked_bars(rows, "worker", grain="year", height=340), rows, "workshop", "workshop_by_worker")

ui.definitions_box("workshop")
