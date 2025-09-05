"""
services/opt_validation.py

Purpose
-------
Human-in-the-loop (HITL) ladder for Screen 5 (Optimization).
Evaluates optimization feasibility and risk signals, assigns a ladder level (L0–L4),
and produces actionable messages plus an acknowledgment record to persist.

Ladder semantics (MVP)
----------------------
- L0: OK — no gating required.
- L1: Heads-up — mild risk; require acknowledgment.
- L2: Elevated — moderate risk; require acknowledgment.
- L3: High — significant risk; require acknowledgment.
- L4: Infeasible — block and return guidance (circuit breaker).

Inputs (generic, screen-agnostic)
---------------------------------
We operate on *counts and metrics* emitted/available at the end of candidate selection:
- candidate_count: int
- selected_count: int
- safety_blocked: int
- novelty_blocked: int
- diversity_min: float   (min pairwise distance within the selected batch; e.g., Gower)
- diversity_eps: float   (threshold for "too similar")
- approx_uncertain_frac: float in [0,1] (share of selected with σ > sigma_hi) or proxy

Thresholds (defaults tuned for MVP)
-----------------------------------
- MIN_SELECTED_OK = 1      : if 0 => L4
- BATCH_FRACTION_LOW = 0.5 : if selected < 0.5 * requested => ≥ L2
- DIVERSITY_EPS = 0.15     : min Gower distance threshold for diversity warnings
- UNCERTAIN_FRAC_HI = 0.6  : ≥60% high-σ points => ≥ L2
- BLOCK_RATE_HI = 0.5      : (safety_blocked + novelty_blocked)/candidate_count ≥ 0.5 => ≥ L3

Public API (≤5 functions)
-------------------------
1) evaluate_hitl_level(metrics: dict, requested_batch: int, thresholds: dict|None) -> (level:int, messages:list[str])
2) require_ack(level:int) -> bool
3) build_ack_record(level:int, messages:list[str], operator:str|None=None) -> dict
4) summarize_for_trace(level:int, metrics:dict) -> dict
5) default_thresholds() -> dict

Notes
-----
- This module is deterministic and UI-agnostic. The screen will call evaluate_hitl_level(...)
  then gate “Next” (writes) until require_ack(level) is satisfied and an ack is provided.
- Keep messages short and specific; the screen may render them in a dialog/modal.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, List


def default_thresholds() -> Dict[str, float]:
    """Return default ladder thresholds for MVP."""
    return {
        "MIN_SELECTED_OK": 1,
        "BATCH_FRACTION_LOW": 0.5,
        "DIVERSITY_EPS": 0.15,
        "UNCERTAIN_FRAC_HI": 0.60,
        "BLOCK_RATE_HI": 0.50,
    }


def evaluate_hitl_level(
    metrics: Dict[str, Any],
    requested_batch: int,
    thresholds: Dict[str, float] | None = None
) -> Tuple[int, List[str]]:
    """
    Compute HITL ladder level (0-4) and messages.

    Parameters
    ----------
    metrics : dict
        {
          "candidate_count": int,
          "selected_count": int,
          "safety_blocked": int,
          "novelty_blocked": int,
          "diversity_min": float | None,
          "diversity_eps": float | None,       # optional override for DIVERSITY_EPS
          "approx_uncertain_frac": float | None
        }
    requested_batch : int
        User-requested batch size (k).
    thresholds : dict | None
        Optional overrides for default thresholds.

    Returns
    -------
    (level:int, messages:list[str])
    """
    t = default_thresholds()
    if thresholds:
        t.update(thresholds)

    msgs: List[str] = []
    level = 0

    cand = int(metrics.get("candidate_count", 0) or 0)
    sel = int(metrics.get("selected_count", 0) or 0)
    s_blk = int(metrics.get("safety_blocked", 0) or 0)
    n_blk = int(metrics.get("novelty_blocked", 0) or 0)
    d_min = metrics.get("diversity_min", None)
    d_eps = float(metrics.get("diversity_eps", t["DIVERSITY_EPS"]))
    u_frac = metrics.get("approx_uncertain_frac", None)

    # L4: infeasible / empty
    if sel < t["MIN_SELECTED_OK"]:
        level = max(level, 4)
        msgs.append("Empty batch: no feasible proposals selected. Relax constraints or broaden bounds.")
        return level, msgs

    # L3: severe block
    block_rate = ((s_blk + n_blk) / cand) if cand > 0 else 0.0
    if block_rate >= t["BLOCK_RATE_HI"]:
        level = max(level, 3)
        msgs.append(f"Severe pruning: {(block_rate*100):.0f}% of pool blocked by safety/novelty.")

    # L2: underfilled batch or high uncertainty
    if requested_batch > 0 and sel < int(t["BATCH_FRACTION_LOW"] * requested_batch):
        level = max(level, 2)
        msgs.append(f"Underfilled batch: {sel}/{requested_batch} selected. Relax constraints for more candidates.")
    if isinstance(u_frac, (int, float)) and u_frac >= t["UNCERTAIN_FRAC_HI"]:
        level = max(level, 2)
        msgs.append(f"High uncertainty: {int(u_frac*100)}% of selected have high σ.")

    # L1: low diversity
    if isinstance(d_min, (int, float)) and d_min < d_eps:
        level = max(level, 1)
        msgs.append(f"Low diversity: min pairwise distance {d_min:.2f} < ε={d_eps:.2f}.")

    # L0: OK if no messages
    return level, msgs


def require_ack(level: int) -> bool:
    """Return True if the ladder level requires human acknowledgment before proceeding."""
    return level >= 1  # L1, L2, L3 require ack; L4 is a hard block handled upstream.


def build_ack_record(level: int, messages: List[str], operator: str | None = None) -> Dict[str, Any]:
    """
    Build a serializable acknowledgment record to append to logs or trace.

    Returns
    -------
    {
      "ack_required": bool,
      "level": int,
      "messages": [...],
      "operator": operator or "unknown",
      "ack_ts": None  # screen fills this when the operator acks
    }
    """
    return {
        "ack_required": require_ack(level),
        "level": int(level),
        "messages": list(messages or []),
        "operator": operator or "unknown",
        "ack_ts": None,
    }


def summarize_for_trace(level: int, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a compact dict of key metrics + level for optimization_trace.json.
    Screen can merge this into the trace payload.
    """
    keys = [
        "candidate_count",
        "selected_count",
        "safety_blocked",
        "novelty_blocked",
        "diversity_min",
        "approx_uncertain_frac",
    ]
    out = {k: metrics.get(k) for k in keys}
    out["hitl_level"] = int(level)
    return out
