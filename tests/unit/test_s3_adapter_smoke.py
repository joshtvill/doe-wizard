# tests/unit/test_s3_adapter_smoke.py
import pandas as pd
from services.s3_adapter import suggest_role_candidates, validate_roles
def test_s3_candidates_and_validate():
    df = pd.DataFrame({"x":[1,2], "cat":["a","b"], "y":[0.1,0.2]})
    c = suggest_role_candidates(df)
    ok, _ = validate_roles(df, {"factors_numeric":["x"], "factors_categorical":["cat"], "response":"y", "group_keys":[]})
    assert "numeric_candidates" in c and ok
