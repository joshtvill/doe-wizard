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

import os, importlib, sys, json
import pandas as pd

ART = "artifacts"
SLUG = "s5retry"

def _cleanup(slug):
    for name in [f"{slug}_optimization_settings.json", f"{slug}_proposals.csv", f"{slug}_optimization_trace.json", f"{slug}_screen5_log.json"]:
        try: os.remove(os.path.join(ART, name))
        except FileNotFoundError: pass

def test_headless_retries_on_empty_feasible_set(monkeypatch):
    _cleanup(SLUG)
    monkeypatch.setenv("DOE_WIZARD_SLUG", SLUG)
    monkeypatch.setenv("DOE_WIZARD_S5_AUTORUN", "1")
    # Force empty space for first pass
    monkeypatch.setenv("DOE_WIZARD_PROFILE_JSON", json.dumps({"columns_profile": []}))
    monkeypatch.setenv("DOE_WIZARD_CHAMPION_JSON", json.dumps({"settings": {}, "model_signature": {}}))

    if "screens.optimization" in sys.modules:
        del sys.modules["screens.optimization"]
    importlib.invalidate_caches()
    importlib.import_module("screens.optimization")

    settings = os.path.join(ART, f"{SLUG}_optimization_settings.json")
    proposals = os.path.join(ART, f"{SLUG}_proposals.csv")
    trace = os.path.join(ART, f"{SLUG}_optimization_trace.json")

    assert os.path.exists(settings)
    assert os.path.exists(proposals)
    assert os.path.exists(trace)
    df = pd.read_csv(proposals)
    assert len(df) >= 1
