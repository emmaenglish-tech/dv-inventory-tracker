# Denver Violins report (`report/`)

The new owner's report: eight pages (Overview, What to expect, Instrument & bow sales, Workshop, Rentals,
Products & other income, Expenses, About the data), each with plain-English headlines, KPI tiles against last year,
charts, and a "Show the numbers" table under every chart.

It replaces `dashboard/`, which keeps running unchanged until cutover.

## The contract: this app only reads

Every number, including the headline sentences, is computed upstream in **denver_violins_data**
(`redesign/loader/report.py`) and written once a day to the `rpt_*` tabs of the **dv_clean** Google Sheet. The app
reads all thirteen tabs in one batched API call, picks rows (basis, period, chart) and draws them. It never sums,
groups or derives anything. `tests/test_read_only.py` fails if aggregation code creeps in.

Need a new number? Add it to `report.py`, not here.

| Tab | What it holds |
|---|---|
| `rpt_overview`, `rpt_sales`, `rpt_workshop`, `rpt_rentals`, `rpt_other`, `rpt_expenses` | Chart data, one long layout: `chart`, `basis`, `grain` (month / year / window / calendar_month), `period`, `period_label`, `series`, `value`, `prior` (same period last year), `partial`, `sort` |
| `rpt_kpis` | Tile values per section × window × basis, with last year's value and the % change |
| `rpt_headlines` | The "short version" sentences |
| `rpt_outlook` | Typical month and usual range per area, next 12 months |
| `rpt_recent_sales` | Instrument and bow sale lines, last full month and this month (no customer names) |
| `rpt_definitions`, `rpt_about` | Plain-English definitions; as-of date |
| `rpt_insights` | AI-written bullets per page and basis (kind good / watch / idea), written weekly by `redesign/loader/insights.py`; shown in a violet "AI insights" card under the short version. Optional: no card until the tab exists |

## Filters (one row, top of every page)

- **Count money**: when invoiced (accrual, default) or when paid (cash).
- **Totals for**: last month, this year so far (default), last 12 months, last year. Tiles and "against last year"
  charts use it.
- **Monthly charts show**: last 12 months, last 2 years (default), since 2021.

## Run it

Against a local copy of the tabs (no Google access needed), built by the pipeline:

```bash
# in denver_violins_data
PYTHONPATH=redesign .venv/bin/python -m loader.run clean --local /tmp/dv_report
# in this repo
pip install -r report/requirements.txt
DV_REPORT_DIR=/tmp/dv_report streamlit run report/app.py
```

Against the real sheet: `DV_SERVICE_ACCOUNT=/path/to/service_account.json streamlit run report/app.py`.

## Deploy (Streamlit Community Cloud)

New app → this repo, branch `main`, main file `report/app.py`. Secrets: the same `[gcp_service_account]` block as
the old dashboard (`emma-bot@…`, which already has access to dv_clean). The data is financial: set the app's
sharing to specific viewers, not public.

## Chart rules

Validated categorical palette, colors fixed per entity (Violin is always blue), at most 8 colors per chart, gray for
"not recorded"; one blue ramp for ordered things (sale sizes, years); one y-axis per chart; "this period" in blue
against last year in gray. Charts and colors live in `lib/charts.py`.
