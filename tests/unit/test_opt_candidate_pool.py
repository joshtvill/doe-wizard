import numpy as np
import pytest

from services.opt_candidate_pool import build_pool, distance_gower, circuit_break_if_empty

SPACE_MIXED = {
    "numeric": {
        "USAGE_OF_MEMBRANE": {"low": 95.0, "high": 120.0, "step": 0.5},
        "PRESSURIZED_CHAMBER_PRESSURE": {"low": 60.0, "high": 90.0, "step": None},
    },
    "categorical": {
        "STAGE": {"allowed": ["A", "B"]},
    },
    "excluded": ["WAFER_ID", "TIMESTAMP"],
}

def test_build_pool_basic_bounds_and_domains():
    pool = build_pool(SPACE_MIXED, n_pool=32, seed=1729)
    assert len(pool) <= 32
    # Bounds respected
    for row in pool:
        assert 95.0 <= row["USAGE_OF_MEMBRANE"] <= 120.0
        assert 60.0 <= row["PRESSURIZED_CHAMBER_PRESSURE"] <= 90.0
        assert row["STAGE"] in ("A", "B")
        # step grid check for USAGE_OF_MEMBRANE
        x = row["USAGE_OF_MEMBRANE"]
        assert abs(((x - 95.0) / 0.5) - round((x - 95.0) / 0.5)) < 1e-9

def test_build_pool_handles_no_categorical():
    space = {
        "numeric": {"X": {"low": 0.0, "high": 1.0, "step": None}},
        "categorical": {},
        "excluded": []
    }
    pool = build_pool(space, n_pool=10, seed=1)
    assert len(pool) == 10
    for r in pool:
        assert 0.0 <= r["X"] <= 1.0

def test_gower_distance_mixed():
    A = [{"X": 0.0, "Y": "A"}, {"X": 1.0, "Y": "B"}]
    B = [{"X": 0.5, "Y": "A"}, {"X": 1.0, "Y": "A"}]
    meta = {"numeric": {"X": {"low": 0.0, "high": 1.0}}, "categorical": {"Y": {"allowed": ["A","B"]}}}
    D = distance_gower(A, B, meta)
    assert D.shape == (2, 2)
    # Standard Gower: average across all compared features (numeric + categorical)
    # A[0] vs B[0]: numeric 0.5, categorical 0 -> (0.5 + 0) / 2 = 0.25
    assert np.isclose(D[0, 0], 0.25)
    # A[1] vs B[0]: numeric 0.5, categorical 1 -> (0.5 + 1) / 2 = 0.75
    assert np.isclose(D[1, 0], 0.75)

def test_circuit_breakers():
    # empty everything
    empty_space = {"numeric": {}, "categorical": {}, "excluded": []}
    with pytest.raises(ValueError):
        circuit_break_if_empty(empty_space)

    # empty categorical domain triggers
    bad_cat = {"numeric": {}, "categorical": {"Y": {"allowed": []}}, "excluded": []}
    with pytest.raises(ValueError):
        circuit_break_if_empty(bad_cat)
