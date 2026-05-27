"""A bow is an instrument.

Reporting groups by Instrument ∈ {Violin, Viola, Cello, Bow} — a bow is just
another instrument category, not a separate axis. The sales/workshop aggregates
carry a bow flag plus an instrument family; collapse them into one
``instrument_group`` dimension here so every page groups the same way. (If we
later want bow broken out by family, that's a future, data-quality-gated step.)
"""
from __future__ import annotations

import pandas as pd

# Canonical display order for the single instrument dimension.
ORDER = ["Violin", "Viola", "Cello", "Bow", "Unknown"]

_FAMILY = {"violin": "Violin", "viola": "Viola", "cello": "Cello"}


def add_instrument_group(df: pd.DataFrame, *, bow_col: str = "bow",
                         instrument_col: str = "instrument",
                         out_col: str = "instrument_group") -> pd.DataFrame:
    """Add ``out_col`` = 'Bow' for bow rows, else the title-cased family
    (Violin/Viola/Cello), else 'Unknown'. Non-destructive (returns a copy)."""
    out = df.copy()
    family = (out[instrument_col].astype(str).str.strip().str.lower()
              .map(_FAMILY).fillna("Unknown"))
    if bow_col in out.columns:
        is_bow = out[bow_col].astype(bool)
        out[out_col] = family.where(~is_bow, "Bow")
    else:
        out[out_col] = family
    return out


def ordered_present(values) -> list[str]:
    """ORDER filtered to the groups actually present (for stable chart legends)."""
    present = set(values)
    return [g for g in ORDER if g in present]
