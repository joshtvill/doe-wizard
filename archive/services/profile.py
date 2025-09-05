# services/profile.py
from __future__ import annotations
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from pandas.api import types as pdt

def _is_numeric(s: pd.Series) -> bool:
    return pdt.is_integer_dtype(s) or pdt.is_float_dtype(s) or pdt.is_numeric_dtype(s)

def _is_datetime(s: pd.Series) -> bool:
    return pdt.is_datetime64_any_dtype(s)

def profile_df(df: pd.DataFrame, sample_rows: int = 1000) -> Dict[str, Any]:
    """
    Quick JSON-friendly profile of a DataFrame.
    Uses up to sample_rows for speed on large tables.
    """
    n_rows, n_cols = df.shape
    sample = df if n_rows <= sample_rows else df.head(sample_rows)

    cols: List[Dict[str, Any]] = []
    for c in sample.columns:
        s = sample[c]
        full = df[c]

        info: Dict[str, Any] = {
            "name": str(c),
            "dtype": str(full.dtype),
            "missing_count": int(full.isna().sum()),
            "missing_pct": float((full.isna().mean() * 100.0) if n_rows else 0.0),
        }

        # cardinality on sample for speed
        try:
            info["unique_count_sample"] = int(s.nunique(dropna=True))
        except Exception:
            info["unique_count_sample"] = None

        # example values (stringified)
        try:
            ex = s.dropna().astype(str).unique().tolist()
        except Exception:
            ex = []
        info["example_values"] = ex[:5]

        # numeric summary (sample)
        if _is_numeric(full):
            try:
                desc = s.describe()  # count, mean, std, min, 25%, 50%, 75%, max
                info.update({
                    "numeric_min_sample": float(desc.get("min", np.nan)),
                    "numeric_max_sample": float(desc.get("max", np.nan)),
                    "numeric_mean_sample": float(desc.get("mean", np.nan)),
                    "numeric_std_sample": float(desc.get("std", np.nan)),
                })
            except Exception:
                pass

        # datetime flag
        info["is_datetime"] = bool(_is_datetime(full))

        cols.append(info)

    return {
        "table": {
            "n_rows": int(n_rows),
            "n_cols": int(n_cols),
            "memory_mb_approx": float(df.memory_usage(deep=True).sum() / 1e6),
            "sample_rows_used": int(len(sample)),
        },
        "columns": cols,
    }
