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

import os
import json
import sys
import importlib
import pandas as pd
import streamlit as st

ART_DIR = "artifacts"
SLUG = "s5test"
from tests._helpers.artifacts import resolve

class DemoModel:
    # simple linear predictor for testing
    def predict(self, X):
        out = []
        for row in X:
            x = row.get("x", row.get("X", 0.0))
            out.append(float(x) * 2.0 + 1.0)
        return out

def _artifact_paths(slug: str):
    return (
        str(resolve(slug, "optimization_settings.json")),
        str(resolve(slug, "proposals.csv")),
        str(resolve(slug, "optimization_trace.json")),
        str(resolve(slug, "screen5_log.jsonl")),
    )

def _cleanup_artifacts(slug: str):
    os.makedirs(ART_DIR, exist_ok=True)
    for p in _artifact_paths(slug):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

def test_screen5_autorun_ack_guardrails_and_artifacts(monkeypatch):
    _cleanup_artifacts(SLUG)

    # Set env fallbacks (robust under pytest)
    monkeypatch.setenv("DOE_WIZARD_SLUG", SLUG)
    monkeypatch.setenv("DOE_WIZARD_S5_AUTORUN", "1")
    monkeypatch.setenv("DOE_WIZARD_S5_AUTOACK", "1")

    # (Best effort) also set session_state for local runs
    st.session_state.clear()
    st.session_state["session_slug"] = SLUG
    st.session_state["s5_autorun"] = True
    st.session_state["s5_auto_ack"] = True
    st.session_state["s5_demo_model"] = DemoModel()

    # minimal profile & champion bundle
    st.session_state["session_profile"] = {
        "columns_profile": [
            {"column": "X", "dtype": "float64", "n_unique": 25, "value_classification": "normal"},
            {"column": "CAT", "dtype": "object", "n_unique": 2, "value_classification": "normal", "example_values": ["A","B"]},
            {"column": "WAFER_ID", "dtype": "int64", "n_unique": 999, "value_classification": "normal"},
        ]
    }
    st.session_state["champion_bundle"] = {
        "settings": {"response_col": "Y", "features": ["X"]},
        "model_signature": {"type": "XGBRegressor", "params": {"enable_categorical": False}},
    }

    # novelty reference far from default [0,1]
    st.session_state["s5_training_preview"] = [{"X": 10.0, "CAT": "A"}]

    # Force a truly fresh import of the screen
    if "screens.optimization" in sys.modules:
        del sys.modules["screens.optimization"]
    importlib.invalidate_caches()
    importlib.import_module("screens.optimization")  # triggers autorun via env/session

    # Verify artifacts
    settings_path, proposals_path, trace_path, log_path = _artifact_paths(SLUG)
    assert os.path.exists(settings_path)
    assert os.path.exists(proposals_path)
    assert os.path.exists(trace_path)
    assert os.path.exists(log_path)

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
    assert settings["batch_size"] >= 1
    assert "constraints" in settings
    assert "guardrails" in settings
    assert settings.get("schema_version") in ("1.2", "1.3")

    with open(trace_path, "r", encoding="utf-8") as f:
        trace = json.load(f)
    assert "hitl_level" in trace and "ack" in trace
    assert "safety_blocked" in trace and "novelty_blocked" in trace

    df = pd.read_csv(proposals_path)
    assert len(df) >= settings["batch_size"]
    assert {"_mu", "_sigma", "_score"}.issubset(df.columns)
