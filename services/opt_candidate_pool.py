"""
services/opt_candidate_pool.py

Purpose
-------
Screen 5: Build a *feasible* mixed-type candidate pool for Bayesian optimization.
- Numeric sampling via Latin Hypercube (LHS).
- Categorical sampling via uniform draws over allowed sets (or fixed/locked singleton).
- Combines numeric + categorical into a single pool of unique dict rows.
- Provides Gower distance for mixed data (used by novelty/diversity downstream).
- Circuit-breaks when the feasible set is empty and explains why.

Context
-------
- Settings fields (batch/acquisition/uncertainty) come from optimization_settings v1; S5 extends the
  settings with constraints, but pool building itself is settings-agnostic. :contentReference[oaicite:4]{index=4}
- Optimization trace later records pool size, diversity kept, blocks, and timing. :contentReference[oaicite:5]{index=5}
- Session profile shows mixed numeric/categorical columns (e.g., STAGE, various numeric knobs). :contentReference[oaicite:6]{index=6}
- Current champion is XGB with enable_categorical=False; sampling can include categories but scoring must respect
  model compatibility (enforced upstream/elsewhere). :contentReference[oaicite:7]{index=7}

Acceptance Criteria
-------------------
1) `build_pool(space, n_pool, seed)` returns a list[dict] with keys = features in `space.numeric` ∪ `space.categorical`.
   - Respects numeric low/high and lock; categorical allowed sets and lock (singleton).
   - Produces up to `n_pool` unique candidates (de-duplicated).
2) `distance_gower(A, B, meta)` returns pairwise Gower distances for lists of dicts (A vs B) using:
   - Numeric: range-scaled absolute differences (per-feature range from space; 0 if range=0).
   - Categorical: 0 if equal else 1 (when feature present in both).
3) `circuit_break_if_empty(space)` raises ValueError with actionable message when no feature is optimizable
   or when a feature has an empty domain (e.g., categorical allowed=[]).
4) ≤5 functions in this file.

Notes
-----
- No external sampling libs; LHS implemented with NumPy.
- Unspecified numeric bounds (None) are not sampled; caller should validate/normalize earlier.
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import numpy as np


# ---------------------------
# Public API (≤5 functions)
# ---------------------------

def build_pool(space: Dict[str, Any], n_pool: int, seed: int | None = None) -> List[Dict[str, Any]]:
    """
    Build a mixed-type candidate pool from `space` produced by `apply_constraints(...)`.

    Parameters
    ----------
    space : dict
        {
          "numeric": {feat: {"low": float|None, "high": float|None, "step": float|None}},
          "categorical": {feat: {"allowed": list|None}},
          "excluded": [...],
          ...
        }
    n_pool : int
        Maximum number of unique candidates to return.
    seed : Optional[int]
        RNG seed.

    Returns
    -------
    List[Dict[str, Any]]

    Raises
    ------
    ValueError: if feasible set is empty (delegates to circuit_break_if_empty)
    """
    circuit_break_if_empty(space)

    rng = np.random.default_rng(seed)

    # ---- Prepare numeric specs ----
    num_feats = []
    num_lows = []
    num_highs = []
    num_steps = []

    for f, spec in (space.get("numeric") or {}).items():
        low = spec.get("low")
        high = spec.get("high")
        step = spec.get("step")
        # Only sample numeric if both bounds are resolved and range is valid (low<=high)
        if low is None or high is None:
            continue
        if float(high) < float(low):
            continue
        num_feats.append(f)
        num_lows.append(float(low))
        num_highs.append(float(high))
        num_steps.append(None if step is None else float(step))

    # ---- Prepare categorical specs ----
    cat_feats = []
    cat_domains = []
    for f, spec in (space.get("categorical") or {}).items():
        allowed = spec.get("allowed")
        # If domain unknown, skip from sampling; it can be set by UI before calling
        if allowed is None:
            continue
        if isinstance(allowed, list) and len(allowed) == 0:
            # Empty domain → infeasible
            raise ValueError(f"[candidate_pool] categorical `{f}` has empty allowed domain.")
        cat_feats.append(f)
        cat_domains.append(list(allowed))

    # ---- LHS for numeric block ----
    num_samples = _sample_numeric_lhs(num_lows, num_highs, num_steps, n_pool, rng) if num_feats else np.zeros((n_pool, 0))

    # ---- Uniform categorical draws ----
    cat_samples = _sample_categorical(cat_domains, n_pool, rng) if cat_feats else [[] for _ in range(n_pool)]

    # ---- Stitch numeric + categorical into dict rows ----
    rows: List[Dict[str, Any]] = []
    seen = set()
    for i in range(n_pool):
        row = {}
        # numeric
        for j, f in enumerate(num_feats):
            row[f] = float(num_samples[i, j])
        # categorical
        if cat_feats:
            for j, f in enumerate(cat_feats):
                row[f] = cat_samples[i][j]
        # Deduplicate (tuples are hashable)
        key = tuple((k, row[k]) for k in sorted(row.keys()))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if len(rows) >= n_pool:
            break

    return rows


def _sample_numeric_lhs(lows: List[float], highs: List[float], steps: List[float | None],
                        n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Latin Hypercube Sampling on a box defined by lows/highs.
    Steps (if provided) are applied by snapping to nearest grid.

    Returns
    -------
    np.ndarray of shape (n, d)
    """
    d = len(lows)
    if d == 0:
        return np.zeros((n, 0))

    # Create LHS strata per dimension
    u = rng.random((n, d))
    strata = (np.arange(n)[:, None] + u) / n  # in (0,1)
    # Independently permute each column
    for j in range(d):
        rng.shuffle(strata[:, j])

    # Scale to bounds
    bounds = np.array([lows, highs])  # shape (2, d)
    scaled = bounds[0] + strata * (bounds[1] - bounds[0])

    # Snap to step grid if provided
    out = np.empty_like(scaled)
    for j in range(d):
        step = steps[j]
        if step is None or step <= 0:
            out[:, j] = scaled[:, j]
        else:
            # snap to nearest multiple of step from low
            off = (scaled[:, j] - lows[j]) / step
            out[:, j] = lows[j] + np.round(off) * step
            # clamp to [low, high]
            out[:, j] = np.clip(out[:, j], lows[j], highs[j])

    return out


def _sample_categorical(domains: List[List[Any]], n: int, rng: np.random.Generator) -> List[List[Any]]:
    """
    Draw n categorical tuples uniformly over each feature domain.
    """
    if not domains:
        return [[] for _ in range(n)]
    d = len(domains)
    out = []
    for _ in range(n):
        tup = [domains[j][rng.integers(0, len(domains[j]))] for j in range(d)]
        out.append(tup)
    return out


def distance_gower(A: List[Dict[str, Any]], B: List[Dict[str, Any]], meta: Dict[str, Any]) -> np.ndarray:
    """
    Compute pairwise Gower distance between lists of candidates A and B.

    Parameters
    ----------
    A, B : list of dict
        Candidate rows with mixed features.
    meta : dict
        {
          "numeric": {feat: {"low": float, "high": float}},
          "categorical": {feat: {"allowed": list}}
        }

    Returns
    -------
    np.ndarray of shape (len(A), len(B))
    """
    aN, bN = len(A), len(B)
    D = np.zeros((aN, bN), dtype=float)

    num = meta.get("numeric", {})
    cat = meta.get("categorical", {})

    num_feats = list(num.keys())
    cat_feats = list(cat.keys())

    # Precompute numeric denominators (range)
    den = []
    for f in num_feats:
        low = num[f].get("low")
        high = num[f].get("high")
        r = (None if (low is None or high is None) else (float(high) - float(low)))
        den.append(0.0 if (r is None or r == 0.0) else r)
    den = np.array(den, dtype=float) if den else np.array([], dtype=float)

    for i in range(aN):
        for j in range(bN):
            s = 0.0
            m = 0  # number of features compared
            # numeric
            for k, f in enumerate(num_feats):
                ai = A[i].get(f)
                bj = B[j].get(f)
                if ai is None or bj is None:
                    continue
                if den.size == 0:
                    continue
                if den[k] == 0.0:
                    diff = 0.0
                else:
                    diff = abs(float(ai) - float(bj)) / den[k]
                s += diff
                m += 1
            # categorical
            for f in cat_feats:
                ai = A[i].get(f)
                bj = B[j].get(f)
                if ai is None or bj is None:
                    continue
                s += 0.0 if ai == bj else 1.0
                m += 1
            D[i, j] = (s / m) if m > 0 else 0.0

    return D


def circuit_break_if_empty(space: Dict[str, Any]) -> None:
    """
    Raise if no optimizable variables exist or any categorical domain is empty.

    - Optimizable if: at least one numeric feature has finite [low, high] with low<=high,
      OR at least one categorical feature has allowed list length >= 1.
    """
    has_numeric = False
    for _, spec in (space.get("numeric") or {}).items():
        low, high = spec.get("low"), spec.get("high")
        if low is not None and high is not None and float(low) <= float(high):
            has_numeric = True
            break

    has_categorical = False
    for f, spec in (space.get("categorical") or {}).items():
        allowed = spec.get("allowed")
        if allowed is not None and len(allowed) >= 1:
            has_categorical = True
        if allowed is not None and len(allowed) == 0:
            raise ValueError(f"[candidate_pool] categorical `{f}` has empty allowed domain.")

    if not (has_numeric or has_categorical):
        raise ValueError(
            "Empty feasible set: no valid numeric ranges and no categorical domains. "
            "Relax constraints, set numeric bounds, or provide categorical allowed sets."
        )
