# tests/unit/test_roles_collapse.py
import pandas as pd

from services.roles import execute_collapse


def test_collapse_min_max_avg_and_last_modes():
    # Two groups by (run_id, station)
    df = pd.DataFrame(
        {
            "run_id": [1, 1, 2, 2],
            "station": ["A", "A", "B", "B"],
            "pad_speed": [50, 60, 70, 80],     # knob varying
            "downforce": [3.0, 3.0, 3.1, 3.1], # knob run-constant
            "slurry_used_l": [0.5, 0.7, 1.0, 1.3], # usage counter
            "t": [10, 20, 5, 15],  # time
            "sample_idx": [1, 2, 1, 2],  # sample order
            "MRR": [0.10, 0.11, 0.20, 0.21], # response
            "trash": ["x", "y", "z", "w"],   # excluded
        }
    )

    grouping_keys = ["run_id", "station"]
    responses = ["MRR"]
    features_roles = {
        "knobs_run_varying": ["pad_speed"],
        "knobs_run_constant": ["downforce"],
        "usage_run_varying": ["slurry_used_l"],
        "excluded": ["trash"],
    }
    collapse_plan_knobs = {
        "pad_speed": "max",  # per contract knobs varying can be min/max/avg
    }
    collapse_plan_usage = {
        "slurry_used_l": "last_by:time",
    }

    collapsed, checks, datacard = execute_collapse(
        df,
        grouping_keys=grouping_keys,
        responses=responses,
        features_roles=features_roles,
        collapse_plan_knobs=collapse_plan_knobs,
        collapse_plan_usage=collapse_plan_usage,
        ordering_time_col="t",
        ordering_sample_col="sample_idx",
    )

    # Expect 2 rows (two groups), columns include keys + pad_speed + downforce + slurry_used_l
    assert len(collapsed) == 2
    cols = set(collapsed.columns)
    assert {"run_id", "station", "pad_speed", "downforce", "slurry_used_l"} <= cols

    # pad_speed=max within each group
    assert float(collapsed.query("run_id==1 and station=='A'")["pad_speed"].iloc[0]) == 60.0
    assert float(collapsed.query("run_id==2 and station=='B'")["pad_speed"].iloc[0]) == 80.0
    # downforce averaged (but constant per group => remains 3.0, 3.1)
    assert float(collapsed.query("run_id==1 and station=='A'")["downforce"].iloc[0]) == 3.0
    assert float(collapsed.query("run_id==2 and station=='B'")["downforce"].iloc[0]) == 3.1
    # last_by:time => take row with larger 't' per group
    assert float(collapsed.query("run_id==1 and station=='A'")["slurry_used_l"].iloc[0]) == 0.7
    assert float(collapsed.query("run_id==2 and station=='B'")["slurry_used_l"].iloc[0]) == 1.3

    # checks + datacard basics
    assert isinstance(checks.get("response_variance_groups"), int)
    assert isinstance(datacard, dict)
    assert datacard["features"]["knobs_run_varying"]["pad_speed"] == "max"
    assert datacard["features"]["usage_run_varying"]["slurry_used_l"] == "last_by:time"


def test_no_grouping_keys_returns_passthrough_minus_excluded():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "trash": ["x", "y"]})
    collapsed, checks, datacard = execute_collapse(
        df,
        grouping_keys=[],  # no collapse
        responses=[],
        features_roles={
            "knobs_run_varying": [],
            "knobs_run_constant": [],
            "usage_run_varying": [],
            "excluded": ["trash"],
        },
        collapse_plan_knobs={},
        collapse_plan_usage={},
    )
    assert len(collapsed) == 2
    assert "trash" not in collapsed.columns
    assert checks["response_variance_groups"] == 0
    assert datacard["grouping_keys"] == []
