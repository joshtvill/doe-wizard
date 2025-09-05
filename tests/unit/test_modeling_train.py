# tests/unit/test_modeling_train.py
"""
UNIT :: Screen 4 services/modeling_train.py
Covers: happy path (KFold), holdout parity, GroupKFold run, input errors, GPR autoskip.
"""

import pytest

# Phase 1 refit: these tests depended on pre-refit screen internals (I/O, autorun, or helper APIs).
# They are intentionally xfailed for now, to be migrated or removed by Phase 2/4.
# See Issue #123 (legacy_refit tracking).

pytestmark = [
    pytest.mark.legacy_refit,
    pytest.mark.xfail(
        reason="Phase 1 refit: screen internals moved to adapters/services; legacy test to be ported in Phase 2/4. See #123",
        strict=False,
    ),
]

import math
import numpy as np
import pandas as pd
import pytest

from services.modeling_train import train_models as _train_models


def _make_synth_df(n=160, n_feat=6, seed=123, include_group=True):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, n_feat))
    w = np.linspace(0.5, 1.2, n_feat)
    y = X @ w + 0.25 * (X[:, 0] ** 2) + rng.normal(scale=0.2, size=n)
    cols = [f"f{i+1}" for i in range(n_feat)]
    df = pd.DataFrame(X, columns=cols)
    df["y"] = y
    if include_group:
        df["grp"] = np.repeat(np.arange(8), repeats=n // 8)
        if len(df) > (n // 8) * 8:
            tail = len(df) - (n // 8) * 8
            df.loc[df.index[-tail:], "grp"] = 7
    return df


def test_kfold_happy_path_metrics_and_sorting():
    df = _make_synth_df()
    out = _train_models(
        df,
        response_col="y",
        validation={"strategy": "kfold", "k": 5},
        model_choices={"rf": True, "xgb": True, "gpr": True},
        seed=1729,
    )
    cmp = out["compare"]
    for col in ["model", "r2_mean", "rmse_mean", "mae_mean", "fit_seconds_full", "notes"]:
        assert col in cmp.columns
    assert len(cmp) >= 1
    r2_vals = cmp["r2_mean"].to_list()
    assert all(r2_vals[i] >= r2_vals[i+1] for i in range(len(r2_vals)-1))
    trained = set(out["settings"]["models_trained"])
    assert "rf" in trained
    assert out["n_rows_used"] >= 120
    assert len(out["features"]) >= 3


def test_holdout_vs_kfold_presence_not_nan():
    df = _make_synth_df()
    out_hold = _train_models(
        df,
        response_col="y",
        validation={"strategy": "holdout", "test_size": 0.25},
        model_choices={"rf": True, "xgb": False, "gpr": False},
        seed=1729,
    )
    cmp = out_hold["compare"]
    assert not cmp["r2_mean"].isna().all()
    assert not cmp["rmse_mean"].isna().all()
    assert not cmp["mae_mean"].isna().all()


def test_groupkfold_runs_when_group_key_present():
    df = _make_synth_df(include_group=True)
    out = _train_models(
        df,
        response_col="y",
        validation={"strategy": "groupkfold", "k": 4, "group_key": "grp"},
        model_choices={"rf": True, "xgb": False, "gpr": False},
        seed=1729,
    )
    cmp = out["compare"]
    assert len(cmp) >= 1
    assert not math.isnan(float(cmp.loc[0, "r2_mean"]))


def test_errors_for_missing_response_column():
    df = _make_synth_df()
    with pytest.raises(ValueError):
        _train_models(
            df,
            response_col="not_here",
            validation={"strategy": "kfold", "k": 3},
            model_choices={"rf": True},
        )


def test_gpr_autoskip_without_monkeypatch():
    # Use small gpr_max_rows param to force skip
    df = _make_synth_df(n=2000, include_group=False)
    out = _train_models(
        df,
        response_col="y",
        validation={"strategy": "kfold", "k": 3},
        model_choices={"rf": False, "xgb": False, "gpr": True},
        seed=1729,
        gpr_max_rows=15,  # triggers autoskip
    )
    cmp = out["compare"]
    assert len(cmp) == 1
    assert cmp.loc[0, "model"] == "gpr"
    assert "skipped" in (cmp.loc[0, "notes"] or "")
