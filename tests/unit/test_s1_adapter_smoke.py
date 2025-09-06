# tests/unit/test_s1_adapter_smoke.py
from services.s1_adapter import compute_slug, validate_session_inputs

def test_s1_compute_slug_makes_string():
    slug = compute_slug("Demo Project", context_tag="CMP-DEV", objective="Maximize", response_metric="MRR", date_str="250101")
    assert isinstance(slug, str) and "250101_demo-project" in slug

def test_s1_validate_session_inputs_contract():
    # Missing fields -> not ok
    ok, errs = validate_session_inputs("", "Maximize", "Continuous", "", "")
    assert not ok and len(errs) >= 1

    # Minimal valid -> ok
    ok2, errs2 = validate_session_inputs("My Run", "Maximize", "Continuous", "CMP-DEV", "MRR")
    assert ok2 and errs2 == []
