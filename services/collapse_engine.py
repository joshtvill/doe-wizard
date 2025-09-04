# services/collapse_engine.py
from __future__ import annotations
from typing import Dict, List, Any, Tuple
import pandas as pd

# Prefer service if present; fall back to pandas
try:
    from services.roles import apply_collapse  # type: ignore
    _HAS_SERVICE = True
except Exception:
    _HAS_SERVICE = False

_RULES = {"avg": "mean", "min": "min", "max": "max", "last": "last"}

def _fallback(df: pd.DataFrame, group_keys: List[str], rule_map: Dict[str, str]) -> pd.DataFrame:
    if not group_keys:
        raise ValueError("Select at least one group-by key.")
    if not rule_map:
        raise ValueError("Assign at least one rule to a non-group column.")
    agg = {}
    for col, rule in rule_map.items():
        if col in group_keys:
            continue
        if rule not in _RULES:
            raise ValueError(f"Unsupported rule: {rule}")
        agg[col] = _RULES[rule]
    if not agg:
        raise ValueError("No applicable columns to aggregate.")
    return df.groupby(group_keys, dropna=False).agg(agg).reset_index()

def run_collapse(df: pd.DataFrame, group_keys: List[str], rule_map: Dict[str, str]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if _HAS_SERVICE:
        try:
            out_df, diag = apply_collapse(df, group_keys, rule_map)  # type: ignore
            return out_df, (diag or {"engine": "roles-service"})
        except Exception:
            pass
    out_df = _fallback(df, group_keys, rule_map)
    diag = {
        "engine": "pandas-fallback",
        "n_in": int(len(df)),
        "n_out": int(len(out_df)),
        "group_keys": list(group_keys),
        "rules_applied": dict(rule_map),
    }
    return out_df, diag
