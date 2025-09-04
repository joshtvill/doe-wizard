# tests/e2e/test_smoke_s1_s3.py
"""
E2E Smoke (Mode A): S1 -> S3 minimal path with join + collapse + profile
- Build tiny in-memory Features and Response tables
- JOIN via services.joiner.left_join
- COLLAPSE via services.roles.execute_collapse
- PROFILE collapsed via services.profiler.profile_table
- Assert basic shapes and required profile keys

No file I/O in Mode A.
"""

import pandas as pd

from services.joiner import left_join
from services.roles import execute_collapse
from services.profiler import profile_table


def _has_any_key(d: dict, *candidates: str) -> bool:
    return any(k in d for k in candidates)


def _get_first(d: dict, *candidates: str):
    for k in candidates:
        if k in d:
            return d[k]
    return None


def test_smoke_join_collapse_then_profile():
    # --- Features (left) ---
    features_df = pd.DataFrame(
        {
            "run_id": [101, 102, 103, 104, 104],
            "station": ["A", "A", "B", "C", "C"],
            "pad_speed": [50, 55, 60, 65, 67],
            "downforce": [3.0, 3.2, 3.1, 3.3, 3.3],
            "slurry_used_l": [0.5, 0.6, 0.7, 0.8, 0.85],
            "t": [1, 2, 3, 4, 5],  # time for ordering
        }
    )

    # --- Response (right) — omit run 104 row on purpose (left_only) ---
    response_df = pd.DataFrame(
        {
            "run_id_resp": [101, 102, 103],
            "MRR": [0.10, 0.12, 0.09],
        }
    )

    # --- S2: JOIN ---
    merged_df, dx = left_join(
        features_df,
        response_df,
        key_pairs=[("run_id", "run_id_resp")],
    )

    assert len(merged_df) == len(features_df)
    assert dx["join_type"] == "left"
    assert 0.0 <= dx["join_rate"] <= 1.0
    assert dx["left_only"] >= 1  # 104 rows missing MRR

    # --- S3: COLLAPSE ---
    grouping_keys = ["run_id", "station"]
    responses = ["MRR"]
    features_roles = {
        "knobs_run_varying": ["pad_speed"],
        "knobs_run_constant": ["downforce"],
        "usage_run_varying": ["slurry_used_l"],
        "excluded": [],  # nothing excluded in this smoke
    }
    collapsed_df, checks, datacard = execute_collapse(
        merged_df,
        grouping_keys=grouping_keys,
        responses=responses,
        features_roles=features_roles,
        collapse_plan_knobs={"pad_speed": "avg"},
        collapse_plan_usage={"slurry_used_l": "last_by:time"},
        ordering_time_col="t",
        ordering_sample_col=None,
    )

    # Expect #rows equal to unique groups
    n_groups = len(pd.DataFrame({"run_id": features_df["run_id"], "station": features_df["station"]}).drop_duplicates())
    assert len(collapsed_df) == n_groups

    # checks + datacard basics
    assert isinstance(checks.get("response_variance_groups"), int)
    assert isinstance(datacard, dict)
    assert "features" in datacard and "collapsed_summary" in datacard

    # --- PROFILE collapsed ---
    prof = profile_table(collapsed_df)

    assert isinstance(prof, dict)
    assert "table_summary" in prof and "columns_profile" in prof

    ts = prof["table_summary"]
    assert isinstance(ts.get("n_rows"), int)
    assert isinstance(ts.get("n_cols"), int)

    cols = prof["columns_profile"]
    assert isinstance(cols, list) and len(cols) >= 1
    sample = cols[0]

    # Minimal expected fields; allow naming variants and optional non-null field
    assert "column" in sample and "dtype" in sample
    nn_val = _get_first(
        sample,
        "non_null",
        "non_null_count",
        "non_nulls",
        "count_nonnull",
        "nonnull",
        "non_na",
        "non_missing",
    )
    if nn_val is not None:
        assert isinstance(nn_val, int)

    assert _has_any_key(sample, "missing_pct", "missing_percent", "pct_missing")
    assert _has_any_key(sample, "nunique_nonnull", "n_unique", "nunique")
    assert "example_values" in sample
