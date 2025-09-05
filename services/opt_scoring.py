"""
services/opt_scoring.py

Purpose
-------
Screen 5: Score feasible candidates and select a batch.
- Provides μ/σ from a model adapter under the chosen uncertainty mode:
    * 'native'        : uses model.predict(...) and model.predict_std(...) if available
    * 'approx_rf'     : uses model.predict(...), synthesizes σ via a lightweight spread proxy
    * 'deterministic' : uses model.predict(...), σ = 0
- Computes acquisition scores: EI / UCB / PI (delegates to opt_core)
- Selects a batch greedily (qEI-like) with diversity re-ranking using Gower distance (delegates to opt_core).

Notes
-----
- `model` is duck-typed: must have predict(X) -> np.ndarray.
- For diversity, we proxy Gower through opt_core to keep a single canonical implementation.
"""

from __future__ import annotations
from typing import Any, Dict, List, Sequence, Tuple
import numpy as np

from services import opt_core  # centralizes acquisition & diversity helpers


# ---------------------------
# Public API (≤5 functions)
# ---------------------------

def predict_mu_sigma(model: Any,
                     X: List[Dict[str, Any]],
                     mode: str = "approx_rf",
                     approx_epsilon: float = 1e-6) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return (mu, sigma) for candidates X using the given `mode`.

    Parameters
    ----------
    model : Any
        Must have `predict(X) -> array_like`. If `mode='native'` and model also has `predict_std(X)`,
        we will use it for σ; otherwise fallback to approx.
    X : list[dict]
        Candidate rows (mixed features already encoded as required by model).
    mode : str
        'native' | 'approx_rf' | 'deterministic'
    approx_epsilon : float
        Small positive floor to avoid zero σ in approx mode.

    Returns
    -------
    (mu, sigma) : Tuple[np.ndarray, np.ndarray] with shapes (n,), (n,)
    """
    if len(X) == 0:
        return np.array([]), np.array([])

    # Predict mean via duck-typed predict(...)
    mu = np.asarray(model.predict(X), dtype=float).reshape(-1)
    n = mu.shape[0]

    if mode == "deterministic":
        sigma = np.zeros(n, dtype=float)
        return mu, sigma

    if mode == "native" and hasattr(model, "predict_std"):
        try:
            sigma = np.asarray(model.predict_std(X), dtype=float).reshape(-1)
            sigma = np.maximum(sigma, 0.0)
            return mu, sigma
        except Exception:
            pass  # fall back to approx

    # Lightweight approximation of σ based on spread around the median of μ
    med = float(np.median(mu))
    sigma = np.abs(mu - med)
    mad = float(np.median(np.abs(mu - med))) or approx_epsilon
    sigma = sigma / mad
    s = float(np.std(mu)) or 1.0
    sigma = np.maximum(sigma * (0.25 * s), approx_epsilon)
    return mu, sigma


def score_acquisition(acq: str,
                      mu: np.ndarray,
                      sigma: np.ndarray,
                      y_best: float,
                      ucb_k: float = 1.96) -> np.ndarray:
    """
    Delegate to opt_core.score_acquisition for EI/UCB/PI.
    """
    # Map qEI → EI for per-point scoring; batch effect is handled by selection stage
    acq = "EI" if (acq or "").upper() == "QEI" else (acq or "").upper()
    return opt_core.score_acquisition(acq, mu, sigma, y_best, ucb_k=ucb_k)


def select_batch(pool: List[Dict[str, Any]],
                 scores: np.ndarray,
                 k: int,
                 diversity_meta: Dict[str, Any] | None = None) -> List[int]:
    """
    Greedy batch selection with diversity re-ranking (max-min on Gower distance).
    Delegates to opt_core.select_batch_greedy_maxmin.
    """
    return opt_core.select_batch_greedy_maxmin(pool, scores, k, diversity_meta)
