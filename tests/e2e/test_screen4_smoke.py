# tests/e2e/test_screen4_smoke.py
"""
E2E SMOKE :: Screen 4 services-level check on real artifact if present.
Looks for either *_modeling_ready.csv or *_collapsed.csv under artifacts/.
Skips gracefully if none found.
"""

import glob
import os
import pandas as pd
import pytest

from services.modeling_train import train_models


def _find_artifact():
    # Prefer modeling_ready; fallback to collapsed
    patterns = [
        os.path.join("artifacts", "*_modeling_ready.csv"),
        os.path.join("artifacts", "*_collapsed.csv"),
    ]
    for pat in patterns:
        paths = glob.glob(pat)
        if paths:
            return paths[0]
    return None


@pytest.mark.skipif(not os.path.isdir("artifacts"), reason="artifacts/ not found")
def test_train_models_on_artifact_if_present():
    path = _find_artifact()
    if path is None:
        pytest.skip("No modeling_ready/collapsed artifact present — skipping smoke.")
    df = pd.read_csv(path)
    # choose last column as response for smoke; UI will expose selector later
    response_col = df.columns[-1]
    out = train_models(
        df,
        response_col=response_col,
        validation={"strategy": "kfold", "k": 3},
        model_choices={"rf": True, "xgb": True, "gpr": True},
        seed=1729,
    )
    cmp = out["compare"]
    assert len(cmp) >= 1
    assert {"model", "r2_mean", "rmse_mean", "mae_mean"}.issubset(set(cmp.columns))
