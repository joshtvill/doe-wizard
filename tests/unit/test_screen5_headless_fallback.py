import os, importlib, sys
import pandas as pd

ART = "artifacts"
SLUG = "s5headless"

def _cleanup(slug):
    for name in [f"{slug}_optimization_settings.json", f"{slug}_proposals.csv", f"{slug}_optimization_trace.json", f"{slug}_screen5_log.json"]:
        try: os.remove(os.path.join(ART, name))
        except FileNotFoundError: pass

def test_headless_autorun_succeeds_without_session_state(monkeypatch):
    _cleanup(SLUG)
    monkeypatch.setenv("DOE_WIZARD_SLUG", SLUG)
    monkeypatch.setenv("DOE_WIZARD_S5_AUTORUN", "1")
    monkeypatch.setenv("DOE_WIZARD_S5_AUTOACK", "1")

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
