import pytest

from services.opt_constraints import (
    infer_space_from_roles,
    validate_constraints,
    apply_constraints,
    encode_for_model,
    is_feasible,
)

# --- Minimal fixtures approximating uploaded dev artifacts (no I/O) ---

SESSION_PROFILE = {
    "columns_profile": [
        {"column": "WAFER_ID", "dtype": "int64", "n_unique": 11, "value_classification": "normal"},
        {"column": "TIMESTAMP", "dtype": "float64", "n_unique": 3059, "value_classification": "high_cardinality"},
        {"column": "STAGE", "dtype": "object", "n_unique": 2, "example_values": ["A", "B"], "value_classification": "normal"},
        {"column": "USAGE_OF_MEMBRANE", "dtype": "float64", "n_unique": 107, "value_classification": "normal"},
        {"column": "AVG_REMOVAL_RATE", "dtype": "float64", "n_unique": 11, "value_classification": "normal"},
    ]
}

CHAMPION = {
    "settings": {
        "response_col": "AVG_REMOVAL_RATE",
        "features": [
            "WAFER_ID",
            "USAGE_OF_MEMBRANE"
        ],
    },
    "model_signature": {
        "type": "XGBRegressor",
        "params": {
            "enable_categorical": False
        }
    }
}

def test_infer_space_excludes_ids_and_response():
    space = infer_space_from_roles(SESSION_PROFILE, CHAMPION)
    # Excluded should contain TIMESTAMP (high-card) and response col
    assert "TIMESTAMP" in space["excluded"]
    assert "AVG_REMOVAL_RATE" not in space["numeric"]
    assert "AVG_REMOVAL_RATE" not in space["categorical"]
    # WAFER_ID is id-like by name → excluded
    assert "WAFER_ID" in space["excluded"]
    # STAGE recognized as categorical
    assert "STAGE" in space["categorical"]
    # Numeric knob present
    assert "USAGE_OF_MEMBRANE" in space["numeric"]

def test_validate_and_apply_numeric_relations_and_locks():
    space = infer_space_from_roles(SESSION_PROFILE, CHAMPION)
    cons_in = {
        "numeric": {
            "USAGE_OF_MEMBRANE": {"relation": ">=", "value": 100.0, "step": 0.5},
        },
        "categorical": {}
    }
    norm = validate_constraints(space, cons_in)
    assert norm["numeric"]["USAGE_OF_MEMBRANE"]["low"] == 100.0
    assert norm["numeric"]["USAGE_OF_MEMBRANE"]["step"] == 0.5

    pruned = apply_constraints(space, norm)
    spec = pruned["numeric"]["USAGE_OF_MEMBRANE"]
    assert spec["low"] == 100.0
    assert spec["step"] == 0.5

def test_validate_categorical_allowed_and_lock_singleton():
    space = infer_space_from_roles(SESSION_PROFILE, CHAMPION)
    cons_in = {
        "categorical": {
            "STAGE": {"allowed": ["A", "B"], "lock": True}
        }
    }
    norm = validate_constraints(space, cons_in)
    assert sorted(norm["categorical"]["STAGE"]["allowed"]) == ["A", "B"]
    pruned = apply_constraints(space, norm)
    # lock collapses to singleton (first element as convention)
    assert isinstance(pruned["categorical"]["STAGE"]["allowed"], list)
    assert len(pruned["categorical"]["STAGE"]["allowed"]) == 1

def test_encode_for_model_requires_lock_when_cat_in_model_features():
    # Put categorical feature into model features to trigger guard
    champ = {
        "settings": {"features": ["USAGE_OF_MEMBRANE", "STAGE"]},
        "model_signature": {"type": "XGBRegressor", "params": {"enable_categorical": False}},
    }
    space = infer_space_from_roles(SESSION_PROFILE, champ)
    norm = validate_constraints(space, {"categorical": {"STAGE": {"allowed": ["A", "B"], "lock": False}}})
    pruned = apply_constraints(space, norm)
    # should raise because STAGE is categorical & in model features but not locked to singleton
    with pytest.raises(ValueError):
        encode_for_model(pruned, champ)

def test_is_feasible_basic():
    space = infer_space_from_roles(SESSION_PROFILE, CHAMPION)
    norm = validate_constraints(space, {
        "numeric": {"USAGE_OF_MEMBRANE": {"low": 90.0, "high": 120.0}},
        "categorical": {"STAGE": {"allowed": ["A", "B"]}}
    })
    pt_ok = {"USAGE_OF_MEMBRANE": 100.0, "STAGE": "A"}
    pt_bad_num = {"USAGE_OF_MEMBRANE": 130.0, "STAGE": "A"}
    pt_bad_cat = {"USAGE_OF_MEMBRANE": 100.0, "STAGE": "C"}

    assert is_feasible(pt_ok, norm) is True
    assert is_feasible(pt_bad_num, norm) is False
    assert is_feasible(pt_bad_cat, norm) is False
