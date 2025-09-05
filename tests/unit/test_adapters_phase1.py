from services import s1_adapter, s3_adapter

def test_auto_slug():
    s = s1_adapter.compute_slug("My Project", date_str="20250101")
    assert s.startswith("my-project-20250101")

def test_s1_validate_inputs():
    ok, errs = s1_adapter.validate_session_inputs("", "Maximize", "Continuous", "", "")
    assert not ok and len(errs) >= 1

def test_s3_roles_need_responses():
    ok, errs = s3_adapter.validate_roles({"responses": []})
    assert not ok
