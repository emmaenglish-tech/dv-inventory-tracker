"""The report app only reads rpt_* rows: no aggregation or derived numbers may creep into it.

Every number belongs upstream in denver_violins_data (redesign/loader/report.py). Run: python -m pytest report/tests
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
FORBIDDEN = r"\.(groupby|sum|mean|median|cumsum|cumprod|rolling|expanding|agg|aggregate|diff|pct_change|resample)\(|pivot_table|\.value_counts\("


def test_no_aggregation_in_the_app():
    hits = [f"{p.relative_to(APP)}:{i}: {line.strip()}"
            for p in APP.rglob("*.py") if "tests" not in p.parts
            for i, line in enumerate(p.read_text().splitlines(), 1) if re.search(FORBIDDEN, line)]
    assert not hits, "compute this upstream in report.py instead:\n" + "\n".join(hits)
