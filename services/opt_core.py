"""
services/opt_core.py
--------------------
Core helpers shared by S5 optimization services.

Centralizes:
- Acquisition scoring (EI/UCB/PI) with safe σ handling
- Greedy diversity re-ranking (max-min on Gower distance)
- Distance proxy (delegates to opt_candidate_pool.distance_gower)

Public functions are intentionally small so other modules can delegate without churn.
"""

from __future__ import annotations
from typing import Any, Dict, List, Sequence, Tuple
import numpy as np

# We proxy distance through the pool module to keep one canonical implementation.
from services.opt_candidate_pool import distance_gower as _distance_gower  # type: ignore[attr-defined]


# ---------------------------
# Acquisition scoring
# ---------------------------

def score_acquisition(acq: str,
                      mu: np.ndarray,
                      sigma: np.ndarray,
                      y_best: float,
                      ucb_k: float = 1.96) -> np.ndarray:
    """
    Compute acquisition scores for maximization.

    EI : (mu - y_best) * Phi(z) + sigma * phi(z), where z = (mu - y_best) / sigma (sigma>0)
    UCB: mu + k * sigma
    PI : Phi(z)

    Handles sigma==0 safely (EI reduces to max(mu-y_best,0), PI=1 if mu>y_best else 0).
    """
    acq = (acq or "").upper()
    mu = np.asarray(mu, dtype=float).reshape(-1)
    sigma = np.asarray(sigma, dtype=float).reshape(-1)
    n = mu.size

    if acq not in ("QEI", "EI", "UCB", "PI"):
        raise ValueError(f"Unknown acquisition '{acq}'")

    # robust normal cdf/pdf
    try:
        erf = np.erf  # type: ignore[attr-defined]
    except AttributeError:
        import math
        erf = np.vectorize(math.erf)

    def Phi(z: np.ndarray) -> np.ndarray:
        return 0.5 * (1.0 + erf(z / np.sqrt(2.0)))

    def phi(z: np.ndarray) -> np.ndarray:
        return (1.0 / np.sqrt(2.0 * np.pi)) * np.exp(-0.5 * z * z)

    out = np.empty(n, dtype=float)
    pos = sigma > 0
    z = np.zeros_like(mu)
    z[pos] = (mu[pos] - y_best) / sigma[pos]

    if acq in ("EI", "QEI"):
        ei = np.zeros_like(mu)
        ei[pos] = (mu[pos] - y_best) * Phi(z[pos]) + sigma[pos] * phi(z[pos])
        ei[~pos] = np.maximum(mu[~pos] - y_best, 0.0)
        out = ei
    elif acq == "UCB":
        out = mu + float(ucb_k) * sigma
    elif acq == "PI":
        pi = np.zeros_like(mu)
        pi[pos] = Phi(z[pos])
        pi[~pos] = (mu[~pos] > y_best).astype(float)
        out = pi

    return out


# ---------------------------
# Diversity (Gower) helpers
# ---------------------------

def distance_gower(A: List[Dict[str, Any]],
                   B: List[Dict[str, Any]],
                   meta: Dict[str, Any]) -> np.ndarray:
    """
    Thin proxy to the canonical mixed-type Gower distance implementation.
    """
    return _distance_gower(A, B, meta)


def select_batch_greedy_maxmin(pool: List[Dict[str, Any]],
                               scores: np.ndarray,
                               k: int,
                               diversity_meta: Dict[str, Any] | None = None) -> List[int]:
    """
    Greedy batch selection with diversity re-ranking (max-min on Gower distance).

    Steps
    -----
    1) Start from the best single candidate by score.
    2) Iteratively add the candidate with the largest *minimum* Gower distance to the
       already selected set (tie-break by score).
    """
    n = len(pool)
    if n == 0 or k <= 0:
        return []
    k = min(k, n)

    idx_sorted = np.argsort(-scores)
    selected: List[int] = [int(idx_sorted[0])]

    if k == 1 or diversity_meta is None:
        return selected

    D_all = distance_gower(pool, pool, diversity_meta)

    while len(selected) < k:
        mask = np.ones(n, dtype=bool)
        mask[selected] = False
        candidates = np.where(mask)[0]
        if candidates.size == 0:
            break

        min_d = np.min(D_all[candidates][:, selected], axis=1)
        # best by distance; if tie, prefer better score
        best_idx = int(candidates[np.argmax(min_d)])
        # tie-break
        ties = np.where(min_d == np.max(min_d))[0]
        if ties.size > 1:
            best_idx = int(candidates[ties[np.argmax(scores[candidates[ties]])]])
        selected.append(best_idx)

    return selected
