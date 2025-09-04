# services/modeling_train.py
"""
SERVICES :: modeling_train.py
Version: v1.1 (2025-09-02)  << patch: exclude group_key from features; gpr_max_rows passthrough
[docstring unchanged for brevity]
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Iterable, Any
from time import perf_counter
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, GroupKFold, train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel

try:
    from xgboost import XGBRegressor  # type: ignore
    _HAS_XGB = True
except Exception:  # pragma: no cover
    XGBRegressor = None  # type: ignore
    _HAS_XGB = False


def _select_features(
    df: pd.DataFrame,
    response_col: str,
    feature_cols: Optional[List[str]] = None,
    drop_cols: Optional[List[str]] = None,
) -> List[str]:
    if response_col not in df.columns:
        raise ValueError(f"response_col '{response_col}' not in DataFrame.")
    drop = set(drop_cols or [])
    drop.add(response_col)

    if feature_cols is not None:
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"feature_cols missing in df: {missing}")
        feats = [c for c in feature_cols if c not in drop]
        if not feats:
            raise ValueError("feature_cols resolves to empty after exclusions.")
        return feats

    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    feats = [c for c in numeric if c not in drop]
    if not feats:
        raise ValueError("No numeric feature columns found. Provide feature_cols.")
    return feats


def _build_estimators(
    random_state: int,
    enable_rf: bool = True,
    enable_xgb: bool = True,
    enable_gpr: bool = True,
    gpr_max_rows: int = 8000,
) -> Dict[str, Any]:
    ests: Dict[str, Any] = {}
    if enable_rf:
        ests["rf"] = RandomForestRegressor(
            n_estimators=200, max_depth=None, random_state=random_state, n_jobs=-1
        )
    if enable_xgb and _HAS_XGB:
        ests["xgb"] = XGBRegressor(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=random_state,
            n_jobs=-1, tree_method="hist",
        )
    if enable_gpr:
        kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=1e-3)
        gpr = Pipeline([
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("gpr", GaussianProcessRegressor(
                kernel=kernel, alpha=1e-6, normalize_y=True,
                n_restarts_optimizer=1, random_state=None
            )),
        ])
        ests["gpr"] = {"estimator": gpr, "gpr_max_rows": gpr_max_rows}
    return ests


def _score_model(
    model_id: str,
    model_spec: Any,
    X: np.ndarray,
    y: np.ndarray,
    strategy: str,
    k: int,
    test_size: float,
    seed: int,
    groups: Optional[np.ndarray],
) -> Dict[str, Any]:
    if model_id == "gpr":
        gpr_cfg = model_spec
        if X.shape[0] > gpr_cfg["gpr_max_rows"]:
            return {
                "model": "gpr",
                "r2_mean": np.nan, "r2_std": np.nan,
                "rmse_mean": np.nan, "rmse_std": np.nan,
                "mae_mean": np.nan, "mae_std": np.nan,
                "fit_seconds_full": 0.0,
                "notes": f"skipped: rows>{gpr_cfg['gpr_max_rows']}",
                "_fitted": None,
            }
        estimator = gpr_cfg["estimator"]
    else:
        estimator = model_spec

    r2s: List[float] = []; rmses: List[float] = []; maes: List[float] = []
    strategy = (strategy or "kfold").lower()

    if strategy == "holdout":
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=test_size, random_state=seed)
        est = estimator
        est.fit(X_tr, y_tr)
        pred = est.predict(X_te)
        r2s.append(r2_score(y_te, pred))
        rmses.append(float(np.sqrt(mean_squared_error(y_te, pred))))
        maes.append(float(mean_absolute_error(y_te, pred)))
    else:
        if strategy == "groupkfold":
            if groups is None:
                raise ValueError("groups must be provided for GroupKFold.")
            splitter = GroupKFold(n_splits=max(2, k)).split(X, y, groups=groups)
        else:
            splitter = KFold(n_splits=max(2, k), shuffle=True, random_state=seed).split(X, y)

        for tr_idx, te_idx in splitter:
            est = estimator
            est.fit(X[tr_idx], y[tr_idx])
            pred = est.predict(X[te_idx])
            r2s.append(r2_score(y[te_idx], pred))
            rmses.append(float(np.sqrt(mean_squared_error(y[te_idx], pred))))
            maes.append(float(mean_absolute_error(y[te_idx], pred)))

    t0 = perf_counter()
    final_est = estimator
    final_est.fit(X, y)
    fit_seconds_full = round(perf_counter() - t0, 4)

    return {
        "model": model_id,
        "r2_mean": float(np.nanmean(r2s)),
        "r2_std": float(np.nanstd(r2s)),
        "rmse_mean": float(np.nanmean(rmses)),
        "rmse_std": float(np.nanstd(rmses)),
        "mae_mean": float(np.nanmean(maes)),
        "mae_std": float(np.nanstd(maes)),
        "fit_seconds_full": fit_seconds_full,
        "notes": "" if not np.isnan(np.nanmean(r2s)) else "no-scores",
        "_fitted": final_est,
    }


def train_models(
    df: pd.DataFrame,
    response_col: str,
    *,
    feature_cols: Optional[List[str]] = None,
    drop_cols: Optional[List[str]] = None,
    validation: Dict[str, Any] = None,
    model_choices: Dict[str, bool] = None,
    seed: int = 1729,
    gpr_max_rows: int = 8000,  # << new: testable skip threshold
) -> Dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("df must be a non-empty DataFrame.")

    validation = validation or {}
    strategy = (validation.get("strategy") or "kfold").lower()
    k = int(validation.get("k", 5))
    test_size = float(validation.get("test_size", 0.2))
    group_key = validation.get("group_key")

    # Ensure group_key is NOT used as a feature
    extra_drops = set(drop_cols or [])
    if group_key and group_key in df.columns:
        extra_drops.add(group_key)

    feats = _select_features(df, response_col, feature_cols, drop_cols=list(extra_drops))

    use_cols = feats + [response_col] + ([group_key] if (group_key and group_key in df.columns) else [])
    sub = df[use_cols].dropna(axis=0, how="any").copy()
    if sub.shape[0] < 10:
        raise ValueError("Too few rows after NA drop; need at least 10 for stable metrics.")

    X = sub[feats].to_numpy(dtype=float, copy=True)
    y = sub[response_col].to_numpy(dtype=float, copy=True)
    groups = sub[group_key].to_numpy() if (group_key and group_key in sub.columns) else None
    if groups is not None and groups.ndim != 1:
        # Defensive: ensure 1-D groups for GroupKFold
        groups = np.asarray(groups).reshape(-1)

    choices = model_choices or {"rf": True, "xgb": True, "gpr": True}
    ests = _build_estimators(
        random_state=seed,
        enable_rf=choices.get("rf", True),
        enable_xgb=choices.get("xgb", True),
        enable_gpr=choices.get("gpr", True),
        gpr_max_rows=gpr_max_rows,
    )

    rows = []; fitted: Dict[str, Any] = {}
    for mid, spec in ests.items():
        row = _score_model(mid, spec, X, y, strategy, k, test_size, seed, groups)
        rows.append({k2: v for k2, v in row.items() if k2 != "_fitted"})
        fitted[mid] = row["_fitted"]

    compare = pd.DataFrame(rows).sort_values(
        by=["r2_mean", "rmse_mean"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)

    return {
        "settings": {
            "response_col": response_col,
            "features": feats,
            "validation": {
                "strategy": strategy, "k": k, "test_size": test_size,
                "group_key": group_key, "seed": seed,
            },
            "models_trained": list(ests.keys()),
        },
        "features": feats,
        "n_rows_used": int(X.shape[0]),
        "compare": compare,
        "fitted": fitted,
    }


# --- Tiny orchestration helper for Screen 4 recompute ------------------------
def recompute_modeling(session_slug: str, modeling_ready_path: str, settings: Dict[str, Any] | None = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Minimal recompute: write model_compare.csv (empty header if needed) and champion_bundle.json stub.
    Uses artifacts writer to attach schema_version; forwards fingerprints from datacard if present.
    """
    from pathlib import Path
    import json
    from services import artifacts as _art
    import pandas as pd  # local import

    sdir = Path("artifacts") / session_slug
    sdir.mkdir(parents=True, exist_ok=True)

    try:
        pd.read_csv(modeling_ready_path)
    except Exception:
        pass

    cmp_path = sdir / "model_compare.csv"
    pd.DataFrame(columns=["model", "r2_mean", "rmse_mean", "mae_mean", "fit_seconds_full", "notes"]).to_csv(cmp_path, index=False)

    datacard = {}
    dpath = sdir / "datacard.json"
    if dpath.exists():
        try:
            datacard = json.loads(dpath.read_text(encoding="utf-8"))
        except Exception:
            datacard = {}
    bundle: Dict[str, Any] = {
        "settings": settings or {},
        "champion_id": "placeholder",
        "champion_metrics": {},
        "models_overview": [],
        "model_signature": {"type": "N/A", "params": {}},
    }
    if datacard.get("dataset_hash"): bundle["dataset_hash"] = datacard["dataset_hash"]
    if datacard.get("roles_signature"): bundle["roles_signature"] = datacard["roles_signature"]
    champ_path = sdir / "champion_bundle.json"
    _art.save_json(bundle, f"{session_slug}_champion_bundle.json")

    return {
        "written": [
            {"artifact": "model_compare.csv", "path": str(cmp_path.resolve())},
            {"artifact": "champion_bundle.json", "path": str(champ_path.resolve())},
        ]
    }
