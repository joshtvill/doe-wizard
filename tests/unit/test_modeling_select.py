# tests/unit/test_modeling_select.py
"""
UNIT :: services/modeling_select.py
Covers: validation, deterministic sorting & tie-breaks, min_r2 warning,
bundle assembly, and error on missing champion in fitted map.
"""

import numpy as np
import pandas as pd
import pytest

from services.modeling_select import select_champion, build_champion_bundle


def _cmp_df():
    # Construct a compact compare table with edge cases:
    # - rf slightly best R2
    # - xgb same R2 as rf but worse RMSE (to trigger tie-break)
    # - gpr has NaNs (should sort last)
    return pd.DataFrame(
        [
            {"model": "rf",  "r2_mean": 0.8123, "rmse_mean": 1.10, "mae_mean": 0.88, "fit_seconds_full": 0.25, "notes": ""},
            {"model": "xgb", "r2_mean": 0.8123, "rmse_mean": 1.12, "mae_mean": 0.90, "fit_seconds_full": 0.20, "notes": ""},
            {"model": "gpr", "r2_mean": np.nan, "rmse_mean": np.nan, "mae_mean": np.nan, "fit_seconds_full": 0.10, "notes": "skipped"},
        ]
    )


def test_select_champion_tie_break_on_rmse_and_rationale_mentions_tie():
    cmp_df = _cmp_df()
    res = select_champion(cmp_df, min_r2=None)
    assert res["champion_id"] == "rf"
    assert isinstance(res["rationale"], list) and res["rationale"]
    # Because rf and xgb share same R2, rationale should reference tie-break
    assert any("Tie on R²" in s for s in res["rationale"])


def test_select_champion_min_r2_warning_triggered():
    cmp_df = _cmp_df().copy()
    # Lower all R2 to force low_r2 warning
    cmp_df["r2_mean"] = [0.35, 0.35, np.nan]
    res = select_champion(cmp_df, min_r2=0.5)
    assert "low_r2" in res["warnings"]


def test_select_champion_requires_columns():
    # Missing rmse_mean should error
    bad = pd.DataFrame([{"model": "rf", "r2_mean": 0.9, "mae_mean": 0.5, "fit_seconds_full": 0.1, "notes": ""}])
    with pytest.raises(ValueError):
        _ = select_champion(bad)


def test_build_champion_bundle_happy_path_and_signature():
    cmp_df = _cmp_df()
    champ = select_champion(cmp_df)
    # dummy fitted map with lightweight estimators (only need get_params)
    class Dummy:
        def __init__(self, name): self.name = name
        def get_params(self, deep=False): return {"alpha": 1.0, "verbose": False, "weird": object()}
    fitted = {row["model"]: Dummy(row["model"]) for _, row in cmp_df.iterrows()}

    settings = {"response_col": "y", "features": ["f1", "f2"], "validation": {"strategy": "kfold", "k": 3}}
    bundle = build_champion_bundle(settings, cmp_df, fitted, champ["champion_id"], include_pickle=False)

    assert bundle["champion_id"] == champ["champion_id"]
    assert "models_overview" in bundle and isinstance(bundle["models_overview"], list)
    sig = bundle["model_signature"]
    assert sig["type"] == "Dummy"
    # non-primitive params should be summarized, not embedded
    assert sig["params"]["weird"].startswith("<")


def test_build_champion_bundle_raises_if_id_missing():
    cmp_df = _cmp_df()
    fitted = {"rf": object()}  # xgb missing on purpose
    with pytest.raises(ValueError):
        _ = build_champion_bundle({}, cmp_df, fitted, "xgb")
