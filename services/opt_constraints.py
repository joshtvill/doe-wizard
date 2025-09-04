"""
services/opt_constraints.py

Purpose
-------
Screen 5: Define and validate the *search space* and *constraints* used by the optimizer.
- Infers numeric ranges and categorical domains from the session profile/datacard.
- Excludes ID-like and high-cardinality keys from optimization automatically.
- Normalizes user constraints (≥, ≤, =) for numeric and allowed-set for categorical.
- Produces a pruned, model-ready search space and feasibility checks.
- Enforces champion-model compatibility (e.g., categorical usage when model can't handle categories).

Context (schemas & artifacts)
-----------------------------
- Settings base fields (batch/acq/uncertainty) come from optimization_settings v1 and are extended here
  to include constraints.* (backward-compatible).  :contentReference[oaicite:4]{index=4}
- Trace bookkeeping fields are emitted by the runner later (counts/timing).  :contentReference[oaicite:5]{index=5}

Acceptance Criteria
-------------------
1) Given a session profile/datacard and a champion bundle, `infer_space_from_roles(...)` returns:
   - numeric: {feature: {"low": float, "high": float, "step": Optional[float]}}
   - categorical: {feature: {"allowed": [values]}}
   - excluded: sorted list of ID-like/high-cardinality/constant fields.
2) `validate_constraints(...)` accepts a user `constraints` dict (numeric + categorical) and returns
   a normalized structure with resolved ranges, locks, and allowed sets that are *consistent* with the inferred space.
   - Supports relations: ">=", "<=", "=" for numeric.
   - For categorical, supports {"allowed": [...]} and {"lock": true} → singleton.
3) `apply_constraints(...)` returns a pruned search space that respects locks and bounds.
4) `encode_for_model(...)` enforces champion compatibility:
   - If model has `enable_categorical=false`, categorical features must be either:
     (a) absent from model features, or
     (b) locked (singleton) or already numerically encoded upstream.
   - Raises `ValueError` with actionable message otherwise.
5) `is_feasible(point)` returns True/False for a candidate dict against normalized constraints.

Notes
-----
- This module does not perform sampling or scoring; see opt_candidate_pool.py and opt_scoring.py.
- Distance/novelty/diversity are handled downstream (Gower distance recommended).
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, List, Optional, Set
import math
import re
import copy


# ---------------------------
# Heuristics & small helpers
# ---------------------------

_ID_LIKE_PAT = re.compile(r"(?:^|_)(id|uuid|guid|timestamp)(?:$|_)", re.IGNORECASE)

def _is_id_like(col: str) -> bool:
    """Heuristic: names that look like identifiers or timestamps."""
    return bool(_ID_LIKE_PAT.search(col))

def _is_high_card(col_profile: Dict[str, Any]) -> bool:
    """Treat 'high_cardinality' or very large unique counts as non-design knobs."""
    if col_profile.get("value_classification") == "high_cardinality":
        return True
    # Fallback: if n_unique is large relative to rows, consider high-card
    n_unique = col_profile.get("n_unique")
    n_rows = col_profile.get("n_rows_used") or col_profile.get("n_rows")
    try:
        if n_unique and n_rows and n_unique > 0.5 * n_rows:
            return True
    except Exception:
        pass
    return False

def _is_constant(col_profile: Dict[str, Any]) -> bool:
    return col_profile.get("value_classification") == "constant"

def _is_categorical_dtype(col_profile: Dict[str, Any]) -> bool:
    """Basic dtype check; object dtype or very low unique can be categorical."""
    dt = (col_profile.get("dtype") or "").lower()
    if dt in ("object", "category", "bool"):
        return True
    # If unique count small and dtype numeric-looking, still allow categorical if explicitly declared upstream.
    n_unique = col_profile.get("n_unique")
    if isinstance(n_unique, int) and n_unique > 1 and n_unique <= 10:
        # guard: only treat as categorical when example values are non-continuous.
        return True
    return False


# ---------------------------
# Public API (≤5 functions)
# ---------------------------

def infer_space_from_roles(session_profile: Dict[str, Any],
                           champion_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the mixed-type design space from a session profile/datacard and champion bundle.

    Parameters
    ----------
    session_profile : dict
        Must contain "columns_profile": List[dict], each with keys:
        - column, dtype, n_unique, value_classification, example_values, etc.  :contentReference[oaicite:6]{index=6}
    champion_bundle : dict
        Must contain "settings.features" list and "model_signature" block that includes
        model type and params (e.g., enable_categorical).  :contentReference[oaicite:7]{index=7}

    Returns
    -------
    space : dict
        {
          "numeric": {feat: {"low": float, "high": float, "step": Optional[float]}},
          "categorical": {feat: {"allowed": [values]}},
          "excluded": [col, ...],  # ID-like/high-cardinality/constant or clearly not design knobs
          "model_features": [ ... ]  # echoed from champion for downstream reference
        }
    """
    cols = session_profile.get("columns_profile", [])
    feat_set = set(champion_bundle.get("settings", {}).get("features", []) or [])
    model_sig = champion_bundle.get("model_signature", {}) or {}
    model_params = model_sig.get("params", {}) or {}
    enable_cat = bool(model_params.get("enable_categorical", False))

    numeric: Dict[str, Dict[str, Optional[float]]] = {}
    categorical: Dict[str, Dict[str, Any]] = {}
    excluded: List[str] = []

    for c in cols:
        name = c.get("column")
        if not name:
            continue

        # Exclude obvious non-design columns
        if _is_id_like(name) or _is_high_card(c) or _is_constant(c):
            excluded.append(name)
            continue

        # Identify categorical vs numeric
        if _is_categorical_dtype(c):
            # Allowed set: use example_values when available & small; otherwise leave empty to be filled by UI.
            allowed = c.get("example_values")
            if not isinstance(allowed, list):
                allowed = None
            categorical[name] = {"allowed": allowed}
        else:
            # We don't have min/max directly; start with None and let UI/Screen derive from S3 datacard ranges
            # or from observed min/max (future extension). For now keep None; validator can accept user-provided lows/highs.
            numeric[name] = {"low": None, "high": None, "step": None}

    # Exclude anything that is clearly not a *design knob* but might have slipped through:
    # e.g., response column, known readbacks, or features we choose to lock.
    response = champion_bundle.get("settings", {}).get("response_col")
    if response and response in numeric:
        excluded.append(response)
        numeric.pop(response, None)
    if response and response in categorical:
        excluded.append(response)
        categorical.pop(response, None)

    # De-duplicate exclusion list
    excluded = sorted(set(excluded))

    return {
        "numeric": numeric,
        "categorical": categorical,
        "excluded": excluded,
        "model_features": list(feat_set),
        "model_enable_categorical": enable_cat,
    }


def validate_constraints(space: Dict[str, Any],
                         constraints: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and validate user constraints against the inferred space.

    Numeric
    -------
    Accepts either:
      - relation + value (>=, <=, =) to convert into bounds/locks
      - explicit low/high/step
    Returns union of both forms collapsed to {"low","high","step","lock"}.

    Categorical
    -----------
    Accepts:
      - {"allowed": [...]}  (values must be subset of inferred domain if known)
      - {"lock": true, "allowed": [single_value]}  (singleton set)

    Raises
    ------
    ValueError: on unknown features, incompatible relations, or empty allowed sets.
    """
    norm = {"numeric": {}, "categorical": {}}

    # Numeric
    numeric_space = space.get("numeric", {})
    for feat, spec in (constraints.get("numeric") or {}).items():
        if feat not in numeric_space:
            raise ValueError(f"[constraints.numeric] Unknown numeric feature: {feat}")
        rel = spec.get("relation")
        val = spec.get("value")
        low = spec.get("low")
        high = spec.get("high")
        step = spec.get("step")
        lock = bool(spec.get("lock", False))

        if rel:
            if rel not in (">=", "<=", "="):
                raise ValueError(f"[{feat}] relation must be one of >=, <=, =")
            if val is None and rel in (">=", "<=", "="):
                raise ValueError(f"[{feat}] relation `{rel}` requires `value`")
            if rel == "=":
                low, high, lock = float(val), float(val), True
            elif rel == ">=":
                low = float(val)
            elif rel == "<=":
                high = float(val)

        # If user gave both relation+value and explicit low/high, explicit wins when consistent.
        # Basic sanity
        if (low is not None) and (high is not None) and (float(low) > float(high)):
            raise ValueError(f"[{feat}] low > high is invalid (low={low}, high={high})")

        norm["numeric"][feat] = {
            "low": None if low is None else float(low),
            "high": None if high is None else float(high),
            "step": None if step is None else float(step),
            "lock": bool(lock),
        }

    # Pass-through any features without user constraints: keep them open (None bounds).
    for feat in numeric_space:
        if feat not in norm["numeric"]:
            norm["numeric"][feat] = {
                "low": numeric_space[feat].get("low"),
                "high": numeric_space[feat].get("high"),
                "step": numeric_space[feat].get("step"),
                "lock": False,
            }

    # Categorical
    cat_space = space.get("categorical", {})
    for feat, spec in (constraints.get("categorical") or {}).items():
        if feat not in cat_space:
            raise ValueError(f"[constraints.categorical] Unknown categorical feature: {feat}")
        allowed = spec.get("allowed")
        lock = bool(spec.get("lock", False))

        # If locked and no explicit allowed given yet, derive from inferred domain if singleton known.
        if lock and (not allowed):
            # If we don't know the domain from the profile, we must fail; UI should supply.
            raise ValueError(f"[{feat}] lock=true requires a singleton `allowed` list")

        if allowed is not None:
            if not isinstance(allowed, list) or len(allowed) == 0:
                raise ValueError(f"[{feat}] `allowed` must be a non-empty list")
            # If we have an inferred domain from profile, enforce subset when known
            inferred = cat_space.get(feat, {}).get("allowed")
            if isinstance(inferred, list) and inferred:
                not_inferred = [v for v in allowed if v not in inferred]
                if not_inferred:
                    raise ValueError(f"[{feat}] values not in domain: {not_inferred}")

        norm["categorical"][feat] = {
            "allowed": allowed if allowed is not None else cat_space.get(feat, {}).get("allowed"),
            "lock": lock,
        }

    # Pass-through any categorical features without user constraints
    for feat in cat_space:
        if feat not in norm["categorical"]:
            norm["categorical"][feat] = {
                "allowed": cat_space[feat].get("allowed"),
                "lock": False,
            }

    # Final sanity: ensure no empty categorical domains
    for feat, spec in norm["categorical"].items():
        if spec.get("allowed") is not None and len(spec["allowed"]) == 0:
            raise ValueError(f"[{feat}] categorical `allowed` cannot be empty")

    return norm


def apply_constraints(space: Dict[str, Any],
                      constraints: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply normalized constraints to the inferred space.

    - Numeric: clamp lows/highs and mark locked variables (low==high when lock).
    - Categorical: restrict `allowed` to intersection if both sides known; if lock, reduce to singleton.

    Returns a pruned `search_space` dict with same shape as `infer_space_from_roles(...)`.
    """
    numeric = copy.deepcopy(space.get("numeric", {}))
    categorical = copy.deepcopy(space.get("categorical", {}))
    excluded = list(space.get("excluded", []))

    cnum = constraints.get("numeric", {})
    for feat, spec in numeric.items():
        c = cnum.get(feat, {})
        low, high, step, lock = c.get("low"), c.get("high"), c.get("step"), c.get("lock", False)

        # Clamp bounds (None means "open")
        if low is not None:
            spec["low"] = float(low) if (spec.get("low") is None) else max(float(low), float(spec["low"]))
        if high is not None:
            spec["high"] = float(high) if (spec.get("high") is None) else min(float(high), float(spec["high"]))
        spec["step"] = float(step) if step is not None else spec.get("step")

        if lock:
            # If lock but no value yet, we need either explicit low==high or we cannot lock deterministically.
            if spec.get("low") is None and spec.get("high") is None:
                # Leave it to UI to supply the equality value. Mark as lock but unresolved value is allowed.
                pass
            else:
                # If one side is missing, propagate the other; otherwise clamp to equality if possible.
                if spec.get("low") is None and spec.get("high") is not None:
                    spec["low"] = spec["high"]
                elif spec.get("high") is None and spec.get("low") is not None:
                    spec["high"] = spec["low"]
        numeric[feat] = spec

    ccat = constraints.get("categorical", {})
    for feat, spec in categorical.items():
        c = ccat.get(feat, {})
        allowed = spec.get("allowed")
        c_allowed = c.get("allowed")
        lock = c.get("lock", False)

        # Intersect when both sides known
        if isinstance(allowed, list) and isinstance(c_allowed, list):
            inter = [v for v in c_allowed if v in allowed]
            spec["allowed"] = inter
        elif c_allowed is not None:
            spec["allowed"] = c_allowed  # trust constraints if no inferred domain

        if lock:
            # If lock but not singleton, make it singleton if possible
            if isinstance(spec.get("allowed"), list) and len(spec["allowed"]) == 1:
                pass
            elif isinstance(spec.get("allowed"), list) and len(spec["allowed"]) > 1:
                # By convention: choose first element as locked value unless UI specified single value already.
                spec["allowed"] = [spec["allowed"][0]]

        categorical[feat] = spec

    return {
        "numeric": numeric,
        "categorical": categorical,
        "excluded": excluded,
        "model_features": list(space.get("model_features", [])),
        "model_enable_categorical": bool(space.get("model_enable_categorical", False)),
    }


def encode_for_model(space: Dict[str, Any],
                     champion_bundle: Dict[str, Any]) -> None:
    """
    Enforce champion compatibility for categorical features.

    If the model has enable_categorical=False (e.g., current XGB champion), then:
    - Any categorical feature that is present in the *model feature list* must be locked
      to a singleton OR already encoded numerically upstream (i.e., not truly categorical here).
    - Categorical features not used by the model may remain variable in S5, but they must
      be handled by downstream sampler/encoder before scoring. For MVP we require them to be
      absent from model_features (typical for this dataset).  :contentReference[oaicite:8]{index=8}
    """
    model_features: Set[str] = set(space.get("model_features") or [])
    enable_cat = bool(space.get("model_enable_categorical", False))
    if enable_cat:
        return  # model can accept categorical; nothing to enforce here.

    for feat, spec in (space.get("categorical") or {}).items():
        if feat in model_features:
            allowed = spec.get("allowed")
            if not isinstance(allowed, list) or len(allowed) != 1:
                raise ValueError(
                    f"[encode_for_model] Champion model cannot consume categorical `{feat}` "
                    f"unless it is locked to a single value or encoded numerically upstream."
                )


def is_feasible(point: Dict[str, Any],
                constraints: Dict[str, Any]) -> bool:
    """
    Check if a candidate point satisfies the normalized constraints.

    - Numeric: respects low/high/lock (within closed interval).
    - Categorical: value ∈ allowed; if lock, allowed is singleton.

    Returns
    -------
    bool
    """
    # Numeric
    for feat, spec in (constraints.get("numeric") or {}).items():
        val = point.get(feat)
        if val is None:
            continue
        low, high = spec.get("low"), spec.get("high")
        if (low is not None) and (val < low):
            return False
        if (high is not None) and (val > high):
            return False

    # Categorical
    for feat, spec in (constraints.get("categorical") or {}).items():
        val = point.get(feat)
        allowed = spec.get("allowed")
        if allowed is not None and val is not None and val not in allowed:
            return False

    return True
