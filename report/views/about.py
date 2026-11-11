import streamlit as st

from lib import data, ui

ui.page_header("About the data", "Where these numbers come from, how fresh they are, and what to keep in mind.")

about = data.about()
if about:
    with st.container(border=True):
        st.markdown("\n".join(f"- **{ui.md(label)}:** {ui.md(detail)}" for label, detail in about.values()))

d = data.tab("rpt_definitions")
names = {"overview": "Overview", "outlook": "What to expect", "sales": "Instrument & bow sales",
         "workshop": "Workshop", "rentals": "Rentals", "other": "Products & other income", "expenses": "Expenses",
         "about": "Where the numbers come from"}
for section in ["about", "overview", "outlook", "sales", "workshop", "rentals", "other", "expenses"]:
    rows = d[d["section"] == section] if not d.empty else d
    if rows.empty:
        continue
    st.subheader(names[section])
    for r in rows.itertuples():
        st.markdown(f"**{ui.md(r.term)}.** {ui.md(r.definition)}")

st.divider()
st.markdown(f"Every chart reads from the [dv_clean Google Sheet]({data.tab_url('rpt_about')}), tabs starting with "
            "`rpt_`. Each chart's *Show the numbers* panel names the tab and rows it uses.")
