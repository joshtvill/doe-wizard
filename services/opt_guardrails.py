"""
services/opt_guardrails.py

Purpose
-------
Guardrail filters for Screen 5 (Optimization).
- Safety: drop candidates whose predicted value is outside a μ±kσ safety band,
          or (in deterministic mode) when a provided absolute limit is violated.
- Novelty: drop candidates that are too close to training data according to Gower distance.
- Diversity: summarize min pairwise distance within a set of selected points (for HITL).

Public API (≤5 functions)
-------------------------
1) apply_safety_filter(mu, sigma, k, mode="approx", abs_limits=None) -> (keep_mask, safety_blocked)
2) apply_novelty_filter(pool, training_X, eps, meta) -> (keep_mask, novelty_blocked)
3) summarize_diversity(pool, selected_idx, meta) -> diversity_min
4) compute_uncertain_fraction(sigma, sigma_hi) -> float in [0,1]
5) build_metrics_dict(candidate_count, selected_idx, safety_blocked, novelty_blocked, diversity_min, approx_uncertain_frac) -> dict

Notes
-----
- `meta` is the same shape used by distance_gower: {"numeric": {...}, "categorical": {...}}
- `abs_limits` (optional): {"low": float|None, "high": float|None} applies only if `mode == "deterministic"`.
- For novelty, we remove points whose min distance to training set is < eps.
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Sequence
import numpy as np

from services.opt_candidate_pool import distance_gower


def apply_safety_filter(mu: np.ndarray,
                        sigma: np.ndarray,
                        k: float,
                        mode: str = "approx",
                        abs_limits: Dict[str, float | None] | None = None) -> Tuple[np.ndarray, int]:
    """
    Safety filter:
    - If mode != 'deterministic': keep candidates whose μ is within μ ± kσ relative to the *batch median*.
      This flags extreme outliers under model uncertainty (σ). Heuristic but stable for MVP.
    - If mode == 'deterministic' and abs_limits provided: keep only low <= μ <= high (when defined).

    Returns
    -------
    keep_mask : np.ndarray[bool]   (length n)
    safety_blocked : int
    """
    mu = np.asarray(mu).reshape(-1)
    sigma = np.asarray(sigma).reshape(-1)
    n = mu.size
    keep = np.ones(n, dtype=bool)

    if mode == "deterministic":
        low = (abs_limits or {}).get("low", None)
        high = (abs_limits or {}).get("high", None)
        if low is not None:
            keep &= mu >= float(low)
        if high is not None:
            keep &= mu <= float(high)
    else:
        med = float(np.median(mu)) if n else 0.0
        band = float(k)
        # keep if |μ - median| <= band * σ  (σ==0 → allow only if μ==median)
        tol = band * sigma
        keep &= np.abs(mu - med) <= tol

    return keep, int((~keep).sum())


def apply_novelty_filter(pool: List[Dict[str, Any]],
                         training_X: List[Dict[str, Any]],
                         eps: float,
                         meta: Dict[str, Any]) -> Tuple[np.ndarray, int]:
    """
    Novelty filter:
    Drop candidates that are within eps of any training point (min Gower distance < eps).

    Returns
    -------
    keep_mask : np.ndarray[bool]
    novelty_blocked : int
    """
    n = len(pool)
    if n == 0 or len(training_X) == 0:
        return np.ones(n, dtype=bool), 0

    D = distance_gower(pool, training_X, meta)  # shape (n, m)
    min_to_train = np.min(D, axis=1) if D.size else np.ones(n, dtype=float)
    keep = min_to_train >= float(eps)
    return keep, int((~keep).sum())


def summarize_diversity(pool: List[Dict[str, Any]],
                        selected_idx: Sequence[int],
                        meta: Dict[str, Any]) -> float | None:
    """
    Compute min pairwise Gower distance within the selected set.
    Returns None if <2 points selected.
    """
    idx = list(selected_idx or [])
    if len(idx) < 2:
        return None
    S = [pool[i] for i in idx]
    D = distance_gower(S, S, meta)
    # ignore diagonal; take min of upper triangle
    n = len(S)
    if n < 2:
        return None
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    vals = D[mask]
    if vals.size == 0:
        return None
    return float(np.min(vals))


def compute_uncertain_fraction(sigma: np.ndarray, sigma_hi: float) -> float:
    """
    Fraction of points with σ >= sigma_hi.
    """
    s = np.asarray(sigma).reshape(-1)
    if s.size == 0:
        return 0.0
    return float(np.mean(s >= float(sigma_hi)))


def build_metrics_dict(candidate_count: int,
                       selected_idx: Sequence[int],
                       safety_blocked: int,
                       novelty_blocked: int,
                       diversity_min: float | None,
                       approx_uncertain_frac: float | None) -> Dict[str, Any]:
    """
    Convenience: assemble the metrics dict used by opt_validation.evaluate_hitl_level(...)
    """
    return {
        "candidate_count": int(candidate_count),
        "selected_count": int(len(selected_idx or [])),
        "safety_blocked": int(safety_blocked),
        "novelty_blocked": int(novelty_blocked),
        "diversity_min": diversity_min,
        "approx_uncertain_frac": approx_uncertain_frac if approx_uncertain_frac is not None else 0.0,
    }
