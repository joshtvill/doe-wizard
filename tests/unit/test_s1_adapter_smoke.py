# tests/unit/test_s1_adapter_smoke.py
from services.s1_adapter import get_form_defaults, compute_slug
def test_s1_defaults_and_slug():
    d = get_form_defaults()
    state = {"project_name": "Demo", "objective": "MRR"}
    slug = compute_slug(state)
    assert isinstance(d, dict) and isinstance(slug, str) and len(slug) > 0
