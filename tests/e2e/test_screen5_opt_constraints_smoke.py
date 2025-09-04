import pytest

from services.opt_constraints import (
    infer_space_from_roles,
    validate_constraints,
    apply_constraints,
    encode_for_model,
)

def test_e2e_opt_constraints_smoke():
    session_profile = {
        "columns_profile": [
            {"column": "WAFER_ID", "dtype": "int64", "n_unique": 11, "value_classification": "normal"},
            {"column": "STAGE", "dtype": "object", "n_unique": 2, "example_values": ["A","B"], "value_classification": "normal"},
            {"column": "USAGE_OF_MEMBRANE", "dtype": "float64", "n_unique": 107, "value_classification": "normal"},
            {"column": "TIMESTAMP", "dtype": "float64", "n_unique": 3059, "value_classification": "high_cardinality"},
            {"column": "AVG_REMOVAL_RATE", "dtype": "float64", "n_unique": 11, "value_classification": "normal"},
        ]
    }
    champion = {
        "settings": {
            "response_col": "AVG_REMOVAL_RATE",
            "features": ["USAGE_OF_MEMBRANE"]  # exclude STAGE from model features for MVP
        },
        "model_signature": {"type": "XGBRegressor", "params": {"enable_categorical": False}},
    }

    # 1) infer
    space = infer_space_from_roles(session_profile, champion)
    assert "USAGE_OF_MEMBRANE" in space["numeric"]
    assert "STAGE" in space["categorical"]
    assert "WAFER_ID" in space["excluded"]
    assert "TIMESTAMP" in space["excluded"]

    # 2) validate
    constraints_in = {
        "numeric": {"USAGE_OF_MEMBRANE": {"relation": ">=", "value": 95.0}},
        "categorical": {"STAGE": {"allowed": ["A","B"]}}
    }
    norm = validate_constraints(space, constraints_in)
    assert norm["numeric"]["USAGE_OF_MEMBRANE"]["low"] == 95.0

    # 3) apply
    pruned = apply_constraints(space, norm)
    assert pruned["numeric"]["USAGE_OF_MEMBRANE"]["low"] == 95.0

    # 4) champion compatibility (no error because STAGE not a model feature)
    encode_for_model(pruned, champion)
