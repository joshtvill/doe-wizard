"""Simple table/column profiler for MVP tests.
Fields per column:
- dtype (pandas dtype name)
- pct_missing (0..1)
- n_unique
- example_values (up to utils.constants.EXAMPLE_VALUES)
- value_classification: one of {'constant','high_cardinality','normal'}
"""
from __future__ import annotations
from typing import Dict, Any
import pandas as pd
import numpy as np

from utils.constants import PROF_SAMPLE_CAP, HIGH_CARD_FRAC, EXAMPLE_VALUES

def _classify(n_unique: int, n: int) -> str:
    if n == 0 or n_unique == 0:
        return "constant"
    if n_unique == 1:
        return "constant"
    if (n_unique / max(n, 1)) > HIGH_CARD_FRAC:
        return "high_cardinality"
    return "normal"

def profile_table(df: pd.DataFrame, sample_cap: int = PROF_SAMPLE_CAP) -> Dict[str, Any]:
    """Return a dict with table_summary and columns_profile list."""
    n_rows, n_cols = df.shape
    if n_rows > sample_cap:
        sample = df.sample(sample_cap, random_state=0)
        sampled = True
        n_rows_used = sample_cap
    else:
        sample = df
        sampled = False
        n_rows_used = n_rows

    table_summary = {
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "sampled": bool(sampled),
        "n_rows_used": int(n_rows_used),
    }

    cols = []
    for col in df.columns:
        s = sample[col]
        n = len(s)
        missing = int(s.isna().sum())
        n_unique = int(s.nunique(dropna=True))
        dtype = str(s.dtype)
        examples = list(s.dropna().unique()[:EXAMPLE_VALUES])
        # Cast to native types for JSON safety
        examples = [ (x.item() if hasattr(x, "item") else x) for x in examples ]

        cols.append({
            "column": col,
            "dtype": dtype,
            "pct_missing": (missing / n) if n else 0.0,
            "n_unique": n_unique,
            "example_values": examples,
            "value_classification": _classify(n_unique, n)
        })

    return {
        "table_summary": table_summary,
        "columns_profile": cols
    }
