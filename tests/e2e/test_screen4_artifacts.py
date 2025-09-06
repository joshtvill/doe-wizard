# tests/e2e/test_screen4_artifacts.py
"""
E2E :: Screen 4 artifacts write/read validation (services-level, UI-compatible).
- Finds either *_modeling_ready.csv or *_collapsed.csv under artifacts/.
- Runs train_models -> select_champion -> build_champion_bundle.
- Writes artifacts via services.artifacts using BASENAMES (to mirror Screen 4).
- Verifies files exist under artifacts/ and validates structure.
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

import glob
import json
import os
from datetime import datetime

import pandas as pd
import pytest

from services.modeling_train import train_models
from services.modeling_select import select_champion, build_champion_bundle
from services.artifacts import save_csv, save_json


def _find_artifact():
    patterns = [
        os.path.join("artifacts", "*_modeling_ready.csv"),
        os.path.join("artifacts", "*_collapsed.csv"),
    ]
    for pat in patterns:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


@pytest.mark.skipif(not os.path.isdir("artifacts"), reason="artifacts/ not found")
def test_screen4_writes_and_reads_artifacts_basename_paths():
    # 1) Load dataset artifact (skip gracefully if none)
    path = _find_artifact()
    if path is None:
        pytest.skip("No modeling_ready/collapsed artifact present — skipping S4 artifact test.")

    df = pd.read_csv(path)
    assert df.shape[0] > 0, "Empty artifact input."

    # 2) Train + select using services
    response_col = df.columns[-1]  # UI exposes selector; smoke uses last column
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

    # 3) Write artifacts via services.artifacts using BASENAMES (mirrors Screen 4)
    slug = f"e2e_s4_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    compare_name = f"{slug}_model_compare.csv"
    bundle_name = f"{slug}_champion_bundle.json"

    os.makedirs("artifacts", exist_ok=True)
    written_compare = save_csv(cmp, compare_name)     # service should resolve to artifacts/<name>
    written_bundle = save_json(pack, bundle_name)

    # 4) Assert files exist under artifacts/ (prefer service-returned path; fallback to default location)
    compare_path = written_compare if isinstance(written_compare, str) else os.path.join("artifacts", compare_name)
    bundle_path = written_bundle if isinstance(written_bundle, str) else os.path.join("artifacts", bundle_name)

    assert os.path.isfile(compare_path), f"model_compare.csv not written at {compare_path}"
    assert os.path.isfile(bundle_path), f"champion_bundle.json not written at {bundle_path}"

    # 5) Read-back validation
    cmp_back = pd.read_csv(compare_path)
    assert {"model", "r2_mean", "rmse_mean", "mae_mean"}.issubset(set(cmp_back.columns))
    assert len(cmp_back) >= 1

    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle_back = json.load(f)

    assert bundle_back.get("champion_id") == sel["champion_id"]
    assert isinstance(bundle_back.get("models_overview"), list)
    assert isinstance(bundle_back.get("champion_metrics"), dict)
    sig = bundle_back.get("model_signature", {})
    assert "type" in sig and isinstance(sig["type"], str)
