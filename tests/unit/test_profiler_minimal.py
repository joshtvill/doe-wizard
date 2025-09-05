import pandas as pd
from services.profiler import profile_table

def test_profile_includes_required_fields():
    df = pd.DataFrame({
        "a":[1,1,1,1],
        "b":[1,2,3,4],
        "c":["x","y","z","x"],
        "d":[None,1,None,2]
    })
    out = profile_table(df, sample_cap=100)
    assert "table_summary" in out and "columns_profile" in out
    cols = {c["column"]:c for c in out["columns_profile"]}
    # dtype, pct_missing, n_unique, example_values, value_classification present
    for k in ["dtype","pct_missing","n_unique","example_values","value_classification"]:
        assert k in cols["a"]
    # Classifications
    assert cols["a"]["value_classification"] == "constant"
    assert cols["b"]["value_classification"] in {"normal", "high_cardinality"}
