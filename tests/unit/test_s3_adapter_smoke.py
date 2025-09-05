# tests/unit/test_s3_adapter_smoke.py
from services.s3_adapter import candidate_role_columns, validate_roles

def test_s3_candidate_role_columns_filters_response_like_names():
    cols = ["x", "cat", "y", "target", "response"]
    cands = candidate_role_columns(cols)
    assert "x" in cands and "cat" in cands
    assert "y" not in cands and "target" not in cands and "response" not in cands

def test_s3_validate_roles_requires_at_least_one_response():
    ok_empty, errs_empty = validate_roles({"responses": []})
    assert not ok_empty and errs_empty

    ok_one, errs_one = validate_roles({"responses": ["y"]})
    assert ok_one and errs_one == []
