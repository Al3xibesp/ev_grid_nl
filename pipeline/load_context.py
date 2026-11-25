"""Context tables collected by hand from CFE, CENACE, the NL Government and the press.

These are small, sourced CSVs in data/context/ (one row per fact, with source and url).
They are read as-is: no estimation happens here, unlike the RAIAVL / VMRC / CENACE pipeline.
"""
from __future__ import annotations

import pandas as pd

from pipeline.config import CONTEXT


def load_context() -> dict[str, pd.DataFrame]:
    """Return the 4 context tables, keyed by short name."""
    reliability = pd.read_csv(CONTEXT / "golfo_norte_reliability.csv")      # yearly SAIDI/SAIFI/CAIDI vs CFE limits
    reference = pd.read_csv(CONTEXT / "grid_reference_values.csv",
                            dtype={"value": str})                          # text: one value is a range ("4-8")
    events = pd.read_csv(CONTEXT / "grid_context_2026.csv", parse_dates=["date"])
    plan = pd.read_csv(CONTEXT / "nl_cfe_plan_2026.csv")
    return {"reliability": reliability, "reference": reference, "events": events, "plan": plan}


def ref_value(reference: pd.DataFrame, metric: str) -> float:
    """One numeric value from grid_reference_values.csv, by metric name."""
    return float(reference.loc[reference["metric"] == metric, "value"].iloc[0])
