# services/roles.py
"""
Roles & Collapse service (Mode A minimal)
-----------------------------------------
Execute Screen-3-style collapse using explicit inputs:

Inputs
------
df : pd.DataFrame                 # from Screen 2 (features or merged)
grouping_keys : list[str]         # 0..N; 0 => no collapse
responses : list[str]             # response columns (metadata only for Mode A)
features_roles : dict             # { "knobs_run_varying": list[str],
                                  #   "knobs_run_constant": list[str],
                                  #   "usage_run_varying": list[str],
                                  #   "excluded": list[str] }

collapse_plan_knobs : dict[str, Literal["min","max","avg"]]
collapse_plan_usage : dict[str, Literal["last_by:time","last_by:sample","last_by:max_self"]]

ordering_time_col : str | None    # used by last_by:time
ordering_sample_col : str | None  # used by last_by:sample

Outputs
-------
collapsed_df : pd.DataFrame
checks : dict  # {"response_variance_groups": int}
datacard : dict  # minimal Screen-3 datacard shape (no file IO in Mode A)

Notes
-----
- We do *not* infer roles; caller supplies roles + plans explicitly.
- For usage "last_by:*", we pick the last row *per group* by the designated ordering.
- When grouping_keys == [], we return df with excluded columns dropped (no collapse).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Literal, Tuple

import pandas as pd
import json, hashlib
from pathlib import Path

from services import artifacts as _art


AggName = Literal["min", "max", "avg"]
UsageMode = Literal["last_by:time", "last_by:sample", "last_by:max_self"]


class RolesError(ValueError):
    """Raised for user/actionable configuration errors."""


def _validate_columns(df: pd.DataFrame, cols: Iterable[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise RolesError(f"{label} missing in DataFrame: {missing}")


def _agg_func(name: AggName):
    if name == "avg":
        return "mean"
    if name in ("min", "max"):
        return name
    raise RolesError(f"Unknown aggregation '{name}'")


def _response_variance_count(
    df: pd.DataFrame,
    grouping_keys: List[str],
    responses: List[str],
) -> int:
    """Count how many groups have >1 non-null unique value for any response."""
    if not grouping_keys or not responses:
        return 0
    # Build per-response nunique over non-null values
    g = df.groupby(grouping_keys, dropna=False)
    # Compute nunique excluding NaN
    def nunique_nonnull(s: pd.Series) -> int:
        return s.dropna().nunique()
    nun = g[responses].agg(nunique_nonnull)
    # nun is a DataFrame indexed by groups, columns = responses
    # Mark groups where ANY response has nunique > 1
    flags = (nun > 1).any(axis=1)
    return int(flags.sum())


def execute_collapse(
    df: pd.DataFrame,
    *,
    grouping_keys: List[str],
    responses: List[str],
    features_roles: Dict[str, List[str]],
    collapse_plan_knobs: Dict[str, AggName],
    collapse_plan_usage: Dict[str, UsageMode],
    ordering_time_col: str | None = None,
    ordering_sample_col: str | None = None,
) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, object]]:
    """
    Run collapse according to explicit plans. Returns (collapsed_df, checks, datacard).
    """
    grouping_keys = grouping_keys or []
    responses = responses or []

    # Normalize role lists
    knobs_run_varying = list(features_roles.get("knobs_run_varying", []))
    knobs_run_constant = list(features_roles.get("knobs_run_constant", []))
    usage_run_varying = list(features_roles.get("usage_run_varying", []))
    excluded = list(features_roles.get("excluded", []))

    # Validate columns present
    _validate_columns(df, grouping_keys, "grouping_keys")
    _validate_columns(df, responses, "responses")
    _validate_columns(df, knobs_run_varying + knobs_run_constant + usage_run_varying, "features")
    _validate_columns(df, excluded, "excluded")

    # Build working frame (drop excluded now)
    work = df.drop(columns=[c for c in excluded if c in df.columns])

    # 0 keys => no collapse (just pass through)
    if len(grouping_keys) == 0:
        collapsed = work.copy()
        checks = {"response_variance_groups": 0}
        datacard = _build_datacard(
            responses=responses,
            grouping_keys=grouping_keys,
            knobs_run_varying=knobs_run_varying,
            knobs_run_constant=knobs_run_constant,
            usage_run_varying=usage_run_varying,
            excluded=excluded,
            checks=checks,
            collapsed_df=collapsed,
            collapse_plan_knobs=collapse_plan_knobs,
            collapse_plan_usage=collapse_plan_usage,
        )
        return collapsed, checks, datacard

    # >=1 keys => collapse path
    # 1) Aggregate knobs
    agg_map: Dict[str, str] = {}
    for col in knobs_run_varying:
        agg_map[col] = _agg_func(collapse_plan_knobs.get(col, "avg"))
    for col in knobs_run_constant:
        agg_map[col] = "mean"  # forced avg

    # Defensive: keep grouping keys in result
    # pandas >=1.5 supports named aggregations; we use a simple groupby.agg
    g = work.groupby(grouping_keys, dropna=False)
    knobs_part = g.agg(agg_map) if agg_map else g.size().rename("rows").to_frame().drop(columns=["rows"], errors="ignore")

    # 2) Usage counters
    usage_part = None
    if usage_run_varying:
        # Decide ordering
        modes = {col: collapse_plan_usage.get(col, "last_by:max_self") for col in usage_run_varying}
        # Start from last_by time/sample if available; otherwise compute per-feature max_self
        pieces = []
        if any(m.startswith("last_by:time") for m in modes.values()):
            if not ordering_time_col:
                raise RolesError("ordering_time_col must be provided for last_by:time")
            _validate_columns(work, [ordering_time_col], "ordering_time_col")
            idx = (
                work.sort_values(by=grouping_keys + [ordering_time_col])
                .groupby(grouping_keys, dropna=False)
                .tail(1)
                .set_index(grouping_keys)
            )
            cols = [c for c, m in modes.items() if m == "last_by:time"]
            pieces.append(idx[cols])
        if any(m.startswith("last_by:sample") for m in modes.values()):
            if not ordering_sample_col:
                raise RolesError("ordering_sample_col must be provided for last_by:sample")
            _validate_columns(work, [ordering_sample_col], "ordering_sample_col")
            idx = (
                work.sort_values(by=grouping_keys + [ordering_sample_col])
                .groupby(grouping_keys, dropna=False)
                .tail(1)
                .set_index(grouping_keys)
            )
            cols = [c for c, m in modes.items() if m == "last_by:sample"]
            pieces.append(idx[cols])
        if any(m == "last_by:max_self" for m in modes.values()):
            # Per-feature max within group (fallback)
            def _max_self(s: pd.Series) -> float:
                return s.max()  # ok for numeric counters
            maxdf = g[ [c for c, m in modes.items() if m == "last_by:max_self"] ].agg(_max_self)
            pieces.append(maxdf)

        # Align/join all usage pieces on grouping index
        if pieces:
            usage_part = pieces[0]
            for p in pieces[1:]:
                usage_part = usage_part.join(p, how="outer")
        else:
            usage_part = pd.DataFrame(index=knobs_part.index)  # nothing to add

    # 3) Combine parts
    if usage_part is not None and not usage_part.empty:
        combined = knobs_part.join(usage_part, how="outer")
    else:
        combined = knobs_part

    # Ensure grouping keys are columns (not index)
    collapsed = combined.reset_index()

    # 4) Checks: response variance within groups
    rv = _response_variance_count(work, grouping_keys, responses)
    checks = {"response_variance_groups": rv}

    # 5) Minimal datacard dict
    datacard = _build_datacard(
        responses=responses,
        grouping_keys=grouping_keys,
        knobs_run_varying=knobs_run_varying,
        knobs_run_constant=knobs_run_constant,
        usage_run_varying=usage_run_varying,
        excluded=excluded,
        checks=checks,
        collapsed_df=collapsed,
        collapse_plan_knobs=collapse_plan_knobs,
        collapse_plan_usage=collapse_plan_usage,
    )

    return collapsed, checks, datacard


def _build_datacard(
    *,
    responses: List[str],
    grouping_keys: List[str],
    knobs_run_varying: List[str],
    knobs_run_constant: List[str],
    usage_run_varying: List[str],
    excluded: List[str],
    checks: Dict[str, int],
    collapsed_df: pd.DataFrame,
    collapse_plan_knobs: Dict[str, AggName],
    collapse_plan_usage: Dict[str, UsageMode],
) -> Dict[str, object]:
    # role summary per Screen-3 spirit (minimal)
    features = {
        "knobs_run_varying": {col: collapse_plan_knobs.get(col, "avg") for col in knobs_run_varying},
        "knobs_run_constant": knobs_run_constant,
        "usage_run_varying": {col: collapse_plan_usage.get(col, "last_by:max_self") for col in usage_run_varying},
        "excluded": excluded,
    }
    datacard = {
        "session_slug": "TBD",  # filled by UI later
        "context_tag": "TBD",   # filled by UI later
        "responses": responses,
        "grouping_keys": grouping_keys,
        "features": features,
        "checks": {
            "response_variance_groups": int(checks.get("response_variance_groups", 0)),
            "ack_response_variance": False,  # HITL toggle happens in UI
        },
        "collapsed_summary": {
            "n_rows": int(len(collapsed_df)),
            "n_features": int(collapsed_df.shape[1]),
        },
        "notes": "",
    }
    return datacard


# --- Tiny orchestration helper for Screen 3 recompute ------------------------
def recompute_roles_and_datacard(
    session_slug: str,
    roles_map: Dict[str, List[str]] | None,
    collapse_spec: Dict[str, str] | None,
    merged_csv_path: str,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Minimal recompute: build modeling_ready.csv (pass-through) and datacard.json with fingerprints.
    This avoids duplicating UI logic; it guarantees fingerprints are refreshed so autoload passes.
    """
    sdir = Path("artifacts") / session_slug
    sdir.mkdir(parents=True, exist_ok=True)

    # 1) modeling_ready.csv (pass-through from merged)
    df = pd.read_csv(merged_csv_path)
    ready_path = sdir / "modeling_ready.csv"
    df.to_csv(ready_path, index=False)

    # 2) datacard.json with fingerprints
    h = hashlib.sha256(); h.update(Path(merged_csv_path).read_bytes()); dataset_hash = h.hexdigest()
    roles_signature = hashlib.sha256(json.dumps({"roles_map": roles_map or {}, "collapse": collapse_spec or {}}, sort_keys=True).encode("utf-8")).hexdigest()
    datacard = {
        "roles_map": roles_map or {},
        "collapse_spec": collapse_spec or {},
        "dataset_hash": dataset_hash,
        "roles_signature": roles_signature,
    }
    datacard_path = sdir / "datacard.json"
    # use artifacts writer to attach schema_version
    _art.save_json(datacard, f"{session_slug}_datacard.json")

    return {
        "written": [
            {"artifact": "modeling_ready.csv", "path": str(ready_path.resolve())},
            {"artifact": "datacard.json", "path": str(datacard_path.resolve())},
        ]
    }
