from services.opt_candidate_pool import build_pool, distance_gower

SPACE = {
    "numeric": {
        "USAGE_OF_MEMBRANE": {"low": 100.0, "high": 110.0, "step": 1.0},
    },
    "categorical": {
        "STAGE": {"allowed": ["A","B"]}
    },
    "excluded": ["WAFER_ID","TIMESTAMP"]
}

def test_e2e_candidate_pool_smoke():
    pool = build_pool(SPACE, n_pool=20, seed=42)
    # correct size and uniqueness
    assert 1 <= len(pool) <= 20
    keys = set()
    for r in pool:
        assert 100.0 <= r["USAGE_OF_MEMBRANE"] <= 110.0
        assert r["STAGE"] in ("A","B")
        keys.add(tuple(sorted(r.items())))
    assert len(keys) == len(pool)

    # distances return a matrix
    D = distance_gower(pool[:5], pool[5:10], {"numeric": SPACE["numeric"], "categorical": SPACE["categorical"]})
    assert D.shape == (5, 5)
