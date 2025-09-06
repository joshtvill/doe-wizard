from services import s1_adapter, s3_adapter

def test_auto_slug():
    # Contract: <YYMMDD>_<Title>-<Context>-<Objective>-<Response>
    s = s1_adapter.compute_slug("My Project", context_tag="", objective="", response_metric="", date_str="250101")
    assert s.startswith("250101_my-project")
    
def test_s1_validate_inputs():
    ok, errs = s1_adapter.validate_session_inputs("", "Maximize", "Continuous", "", "")
    assert not ok and len(errs) >= 1

def test_s3_roles_need_responses():
    ok, errs = s3_adapter.validate_roles({"responses": []})
    assert not ok
