"""Page building blocks: headline box, KPI tiles, chart cards with a table view, definitions."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import charts, data

WINDOW_NAMES = {"last_month": "Last month", "ytd": "This year so far", "ttm": "Last 12 months",
                "last_year": "Last year"}


def money(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    a, sign = abs(v), "−" if v < 0 else ""
    if a >= 1_000_000:
        return f"{sign}${a / 1_000_000:.2f}M"
    if a >= 100_000:
        return f"{sign}${a / 1_000:.0f}k"
    if a >= 10_000:
        return f"{sign}${a / 1_000:.1f}k"
    return f"{sign}${a:,.0f}"


def fmt(v, kind: str) -> str:
    if v is None or pd.isna(v):
        return "—"
    return {"usd": money(v), "count": f"{v:,.0f}", "pct": f"{v:.0%}"}.get(kind, f"{v:,.0f}")


def md(text: str) -> str:
    """Escape dollar signs: Streamlit markdown reads a pair of them as LaTeX math."""
    return str(text).replace("$", "\\$")


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)


def headline_box(section: str) -> None:
    lines = data.headlines(section)
    if not lines:
        return
    with st.container(border=True):
        st.markdown("**The short version**")
        st.markdown("\n".join(f"- {md(t)}" for t in lines))


def kpi_row(section: str, metrics: list[str], inverse: set[str] = frozenset(), window: str | None = None,
            caption: bool = True) -> None:
    """Stat tiles: the value, and the change against the same period last year."""
    rows = [data.kpi(section, m, window) for m in metrics]
    rows = [r for r in rows if r is not None]
    if not rows:
        return
    for col, r in zip(st.columns(len(rows)), rows):
        delta, color = None, "off"
        if r["fmt"] != "pct" and not pd.isna(r["change_pct"]):
            delta = f"{r['change_pct']:+.0%} vs {r['prior_label']}"
            color = "inverse" if r["metric"] in inverse else "normal"
        help_text = " ".join(x for x in (r["note"], f"{r['prior_label']}: {fmt(r['prior'], r['fmt'])}.") if x)
        col.metric(r["label"], fmt(r["value"], r["fmt"]), delta=delta, delta_color=color, help=help_text,
                   border=True)
    if caption:
        st.caption(f"{rows[0]['window_label']} compared with {rows[0]['prior_label']}.")


def _table(rows: pd.DataFrame, money_values: bool) -> pd.DataFrame:
    """Reshape (no arithmetic) for the 'Show the numbers' view."""
    if rows.empty:
        return rows
    order = rows.drop_duplicates("series").sort_values("sort")["series"].tolist()
    if rows["grain"].iloc[0] == "window":
        t = rows.set_index("series").loc[order, ["value", "prior"]]
        return t.rename(columns={"value": rows["period_label"].iloc[0], "prior": "Same period last year"})
    t = rows.pivot(index="period", columns="series", values="value")[order]
    labels = rows.drop_duplicates("period").set_index("period")["period_label"]
    t.index = labels.loc[t.index]
    t.index.name = ""
    return t.iloc[::-1]  # newest first


def chart_card(title: str, read: str, fig, rows: pd.DataFrame, section: str, chart_id: str,
               note: str | None = None, money_values: bool = True, key: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{md(title)}**")
        st.caption(md(read))
        if rows.empty:
            st.info("No data for this view yet.")
            return
        st.plotly_chart(fig, width="stretch", config=charts.config(), key=key or f"{section}-{chart_id}")
        if note:
            st.caption(md(note))
        with st.expander("Show the numbers"):
            t = _table(rows, money_values)
            st.dataframe(t, width="stretch", column_config={
                c: st.column_config.NumberColumn(format="dollar" if money_values else "localized")
                for c in t.columns})
            tab = f"rpt_{section}"
            st.caption(f"Source: [dv_clean › {tab}]({data.tab_url(tab)}), rows where chart = `{chart_id}`.")


def definitions_box(section: str) -> None:
    d = data.definitions(section)
    if d.empty:
        return
    with st.expander("What these numbers mean"):
        for r in d.itertuples():
            st.markdown(f"**{md(r.term)}.** {md(r.definition)}")


def partial_note() -> str:
    return "The lighter bar is the current month, still in progress."
