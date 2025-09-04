# services/modeling_select.py
"""
SERVICES :: modeling_select.py
Version: v1 (2025-09-02)

Purpose
-------
Champion selection and bundle assembly for Screen 4 (Modeling).
- Consumes the outputs of services.modeling_train.train_models(...).
- Encodes deterministic tie-break rules and emits a rationale.

Inputs (expected)
-----------------
- compare_df : pandas.DataFrame with columns:
    ["model","r2_mean","r2_std","rmse_mean","rmse_std",
     "mae_mean","mae_std","fit_seconds_full","notes"]
- settings   : dict returned by train_models()["settings"]
- fitted     : dict[str, estimator] returned by train_models()["fitted"]

Selection Rules (in order)
--------------------------
1) Highest r2_mean
2) If tie (±1e-12), lowest rmse_mean
3) If tie, lowest fit_seconds_full
4) If tie, first by stable alphabetical model id

Optional threshold
------------------
- min_r2: float | None
  If set and best r2_mean < min_r2 → flag "low_r2" in warnings.

Outputs
-------
select_champion(compare_df, min_r2=None) -> dict:
{
  "champion_id": str,
  "champion_row": dict[str, float|str],
  "rationale": list[str],
  "warnings": list[str]
}

build_champion_bundle(settings, compare_df, fitted, champion_id, include_pickle=False) -> dict:
{
  "settings": {...},
  "champion_id": str,
  "champion_metrics": {...},
  "models_overview": compare_df (as records),
  "model_signature": {...},           # small, JSON-safe view of the estimator
  "pickle_included": False,           # this module does NOT pickle; screen/service above can handle I/O
}

Acceptance Criteria
-------------------
- Pure business logic (no Streamlit), deterministic ordering.
- ≤ 5 functions in this module.
- JSON-safe bundle (no raw estimator objects stored).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────────────
# 1) Validation ─ ensure required columns exist
# ──────────────────────────────────────────────────────────────────────────────
def _validate_compare(df: pd.DataFrame) -> None:
    req = {
        "model",
        "r2_mean",
        "rmse_mean",
        "mae_mean",
        "fit_seconds_full",
        "notes",
    }
    missing = [c for c in req if c not in df.columns]
    if missing:
        raise ValueError(f"compare_df missing required columns: {missing}")
    if df.empty:
        raise ValueError("compare_df is empty.")


# ──────────────────────────────────────────────────────────────────────────────
# 2) Sort with deterministic tie-breakers
# ──────────────────────────────────────────────────────────────────────────────
def _sorted_compare(df: pd.DataFrame) -> pd.DataFrame:
    # Stable sort by: r2 desc, rmse asc, fit_seconds asc, model id asc
    out = df.copy()
    # Replace NaNs with sentinel so NaN rows fall to the bottom deterministically
    out["r2_mean_fill"] = out["r2_mean"].fillna(-np.inf)
    out["rmse_mean_fill"] = out["rmse_mean"].fillna(np.inf)
    out["fit_seconds_full_fill"] = out["fit_seconds_full"].fillna(np.inf)
    out["model_fill"] = out["model"].astype(str)

    out = out.sort_values(
        by=["r2_mean_fill", "rmse_mean_fill", "fit_seconds_full_fill", "model_fill"],
        ascending=[False, True, True, True],
        kind="mergesort",  # stable
        na_position="last",
    ).reset_index(drop=True)

    return out.drop(columns=["r2_mean_fill", "rmse_mean_fill", "fit_seconds_full_fill", "model_fill"])


# ──────────────────────────────────────────────────────────────────────────────
# 3) Public API: select champion + rationale
# ──────────────────────────────────────────────────────────────────────────────
def select_champion(compare_df: pd.DataFrame, min_r2: float | None = None) -> Dict[str, Any]:
    """
    Choose champion row using deterministic tie-break rules and emit rationale/warnings.
    """
    _validate_compare(compare_df)
    ordered = _sorted_compare(compare_df)

    champ_row = ordered.iloc[0].to_dict()
    champ_id = str(champ_row["model"])

    rationale: List[str] = []
    warnings: List[str] = []

    # Rationale lines
    rationale.append(f"Selected '{champ_id}' with highest R² mean = {champ_row['r2_mean']:.4f}.")
    # If a tie is plausible within floating tolerance, explain tie-breakers
    # (We check neighbors only when there are ≥2 rows.)
    if len(ordered) >= 2:
        top = ordered.iloc[0]
        second = ordered.iloc[1]
        tol = 1e-12
        if np.isclose(top["r2_mean"], second["r2_mean"], atol=tol):
            rationale.append(
                "Tie on R²; broke tie using lower RMSE, then lower fit time, then model id."
            )

    # Threshold warnings (optional)
    if (min_r2 is not None) and (np.isfinite(champ_row.get("r2_mean", np.nan))):
        if champ_row["r2_mean"] < float(min_r2):
            warnings.append("low_r2")

    # Propagate any model-specific notes
    if (champ_row.get("notes") or "").strip():
        warnings.append(f"notes:{champ_row['notes']}")

    return {
        "champion_id": champ_id,
        "champion_row": champ_row,
        "rationale": rationale,
        "warnings": warnings,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4) Minimal, JSON-safe model signature (no heavy objects)
# ──────────────────────────────────────────────────────────────────────────────
def _model_signature(estimator: Any) -> Dict[str, Any]:
    """Extract a light-weight signature. Avoids deep params to keep JSON small."""
    try:
        params = estimator.get_params(deep=False)
        # Keep only simple types
        simple: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, (int, float, str, bool, type(None))):
                simple[k] = v
            else:
                # summarize non-primitive
                simple[k] = f"<{type(v).__name__}>"
    except Exception:
        simple = {}

    return {
        "type": type(estimator).__name__,
        "params": simple,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5) Public API: build champion bundle (no pickling here)
# ──────────────────────────────────────────────────────────────────────────────
def build_champion_bundle(
    settings: Dict[str, Any],
    compare_df: pd.DataFrame,
    fitted: Dict[str, Any],
    champion_id: str,
    *,
    include_pickle: bool = False,  # this module does NOT create files; caller handles I/O
) -> Dict[str, Any]:
    """
    Assemble a JSON-safe bundle for saving and handoff.
    """
    if champion_id not in fitted:
        raise ValueError(f"champion_id '{champion_id}' not found in fitted models.")
    champ_est = fitted[champion_id]
    champ_metrics = (
        compare_df.loc[compare_df["model"] == champion_id].iloc[0].to_dict()
        if "model" in compare_df.columns and not compare_df.empty
        else {}
    )

    bundle = {
        "settings": settings,
        "champion_id": champion_id,
        "champion_metrics": champ_metrics,
        "models_overview": compare_df.to_dict(orient="records"),
        "model_signature": _model_signature(champ_est),
        "pickle_included": bool(include_pickle),
    }
    return bundle
