"""
services/opt_registry.py
--------------------------------
Central registry for Optimization (S5):
- Allowed acquisitions
- Allowed uncertainty modes
- Lightweight normalization/validation of settings

This module is *not* called by services automatically (to avoid churn).
Screens or runners may import and call normalize_settings(...) when desired.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple


# ---- Public constants ----

ACQUISITIONS = {"qEI", "EI", "UCB", "PI"}
UNCERTAINTY_MODES = {"native", "approx_rf", "deterministic"}


# ---- Public helpers ----

def normalize_settings(settings: Dict[str, Any]) -> Tuple[Dict[str, Any], list[str]]:
    """
    Normalize/validate S5 settings from UI or orchestration.

    Input
    -----
    settings : dict
      {
        "acquisition": str,          # one of ACQUISITIONS (case-insensitive)
        "ucb_k": float,              # >0 when acquisition == "UCB"
        "uncertainty_mode": str,     # one of UNCERTAINTY_MODES (case-insensitive)
        "batch_size": int,           # >0 suggested
        "seed": int,                 # any int
        ... (ignored keys are carried through untouched)
      }

    Returns
    -------
    (normalized, warnings)
      normalized : dict with same keys as input (plus 'acquisition_for_scoring')
      warnings   : list[str] with non-fatal notices

    Notes
    -----
    - We retain the original acquisition for audit/export but also return
      'acquisition_for_scoring' where 'qEI' is mapped to 'EI' for per-point scoring.
    - This function does not raise unless an invalid choice is provided.
    """
    out = dict(settings or {})
    warnings: list[str] = []

    # acquisition
    acq_raw = str(out.get("acquisition", "")).strip()
    acq_upper = acq_raw.upper() if acq_raw else ""
    if acq_upper not in {a.upper() for a in ACQUISITIONS}:
        raise ValueError(f"[opt_registry] Unknown acquisition '{acq_raw}'. Allowed: {sorted(ACQUISITIONS)}")
    out["acquisition"] = acq_raw if acq_raw in ACQUISITIONS else acq_upper if acq_upper in ACQUISITIONS else acq_raw
    # scoring alias
    out["acquisition_for_scoring"] = "EI" if acq_upper == "QEI" else acq_upper

    # uncertainty
    um_raw = str(out.get("uncertainty_mode", "")).strip()
    um_lower = um_raw.lower() if um_raw else ""
    if um_lower not in {m.lower() for m in UNCERTAINTY_MODES}:
        raise ValueError(f"[opt_registry] Unknown uncertainty_mode '{um_raw}'. Allowed: {sorted(UNCERTAINTY_MODES)}")
    out["uncertainty_mode"] = um_raw if um_raw in UNCERTAINTY_MODES else um_lower

    # ucb_k
    ucb_k = out.get("ucb_k", None)
    if out["acquisition_for_scoring"] == "UCB":
        try:
            if float(ucb_k) <= 0:
                raise ValueError  # handled below
        except Exception:
            raise ValueError("[opt_registry] `ucb_k` must be a positive number when acquisition is UCB.")
    else:
        # Not used; keep but warn if provided and weird
        try:
            if ucb_k is None:
                pass
            else:
                float(ucb_k)  # sanity parse
        except Exception:
            warnings.append("`ucb_k` ignored for non-UCB acquisition.")

    # batch_size (non-fatal guidance)
    try:
        if int(out.get("batch_size", 0)) <= 0:
            warnings.append("Batch size is non-positive; consider setting a positive integer.")
    except Exception:
        warnings.append("Batch size is not an integer; using as-is.")

    # seed (no constraints)
    return out, warnings
