"""The AI insights card: shown only when rpt_insights has rows for the page and basis, and clearly labeled as AI.

Run: python -m pytest report/tests
"""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1]
SCRIPT = f"""
import sys
sys.path.insert(0, {str(APP)!r})
import streamlit as st
from lib import ui
st.cache_data.clear()  # each test points DV_REPORT_DIR at its own folder
ui.headline_box("overview")
"""
WRITTEN = dict(generated_at="2026-11-09 14:05", data_as_of="2026-11-09", model="claude-opus-5-5")


@pytest.fixture
def folder(tmp_path, monkeypatch):
    pd.DataFrame([dict(section="overview", basis="accrual", sort=0, text="Revenue is **$10k**.")]
                 ).to_csv(tmp_path / "rpt_headlines.csv", index=False)
    monkeypatch.setenv("DV_REPORT_DIR", str(tmp_path))
    return tmp_path


def run(basis="accrual") -> AppTest:
    at = AppTest.from_string(SCRIPT)
    at.session_state["basis"] = basis
    return at.run()


def test_card_shows_this_page_and_basis_in_order(folder):
    pd.DataFrame([
        dict(section="overview", basis="accrual", sort=1, kind="watch", text="Costs are up $2k.", **WRITTEN),
        dict(section="overview", basis="accrual", sort=0, kind="good", text="Rentals are up 28%.", **WRITTEN),
        dict(section="overview", basis="cash", sort=0, kind="idea", text="A cash-view bullet.", **WRITTEN),
        dict(section="sales", basis="accrual", sort=0, kind="idea", text="A sales-page bullet.", **WRITTEN),
    ]).to_csv(folder / "rpt_insights.csv", index=False)
    at = run()
    assert not at.exception
    text = [m.value for m in at.markdown]
    assert "**The short version**" in text
    assert any("AI insights" in t for t in text)
    bullets = next(t for t in text if "Going well" in t)
    assert bullets.index("Going well") < bullets.index("Keep an eye on")  # sorted by `sort`
    assert "Costs are up \\$2k." in bullets  # $ escaped, not read as LaTeX
    assert "cash-view" not in bullets and "sales-page" not in bullets
    assert at.caption[0].value.startswith("Written Nov 9, 2026 from data through Nov 9, 2026. AI-generated")

    cash = [m.value for m in run("cash").markdown]
    assert any("A cash-view bullet." in t for t in cash) and not any("Rentals are up" in t for t in cash)


@pytest.mark.parametrize("tab", [None, "", "section,basis,sort,kind,text,generated_at,data_as_of,model\n"])
def test_no_card_without_insights(folder, tab):
    """Missing tab, blank tab, or header only (no rows yet): no card, and the short version still shows."""
    if tab is not None:
        (folder / "rpt_insights.csv").write_text(tab)
    at = run()
    assert not at.exception
    text = [m.value for m in at.markdown]
    assert "**The short version**" in text and not any("AI insights" in t for t in text)
