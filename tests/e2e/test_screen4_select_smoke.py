# tests/e2e/test_screen4_select_smoke.py
"""
E2E SMOKE :: Screen 4 selection pipeline on real artifact if present.
- Finds either *_modeling_ready.csv or *_collapsed.csv under artifacts/.
- Runs train_models -> select_champion -> build_champion_bundle.
- Asserts structure only (no file I/O here).
"""

import glob
import os
import pandas as pd
import pytest

from services.modeling_train import train_models
from services.modeling_select import select_champion, build_champion_bundle


def _find_artifact():
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
def test_end_to_end_selection_smoke():
    path = _find_artifact()
    if path is None:
        pytest.skip("No modeling_ready/collapsed artifact present — skipping smoke.")
    df = pd.read_csv(path)

    response_col = df.columns[-1]  # UI will expose selector; this is just a smoke default
    bundle = train_models(
        df,
        response_col=response_col,
        validation={"strategy": "kfold", "k": 3},
        model_choices={"rf": True, "xgb": True, "gpr": True},
        seed=1729,
    )
    cmp = bundle["compare"]
    sel = select_champion(cmp, min_r2=None)
    pack = build_champion_bundle(bundle["settings"], cmp, bundle["fitted"], sel["champion_id"], include_pickle=False)

    assert isinstance(sel["champion_id"], str) and sel["champion_id"]
    assert "champion_metrics" in pack and isinstance(pack["champion_metrics"], dict)
    assert "model_signature" in pack and "type" in pack["model_signature"]
    assert "models_overview" in pack and isinstance(pack["models_overview"], list)
