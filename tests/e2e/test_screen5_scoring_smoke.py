import numpy as np

from services.opt_scoring import predict_mu_sigma, score_acquisition, select_batch

class DemoModel:
    def predict(self, X):
        # simple: y = 2*x + 1 (if present)
        return np.array([2.0 * row.get("x", 0.0) + 1.0 for row in X], dtype=float)

def test_e2e_scoring_smoke():
    # pool from candidate builder would look like list[dict]; we fake a small one
    pool = [{"x": x, "cat": ("A" if (i % 2 == 0) else "B")} for i, x in enumerate([0.0, 0.5, 1.0, 1.5, 2.0])]
    meta = {"numeric": {"x": {"low": 0.0, "high": 2.0}}, "categorical": {"cat": {"allowed": ["A","B"]}}}

    model = DemoModel()
    mu, sigma = predict_mu_sigma(model, pool, mode="approx_rf")  # XGB-like path (no native σ)
    y_best = float(np.max(mu)) - 0.5  # pretend the current best is slightly below the top
    scores = score_acquisition("EI", mu, sigma, y_best, ucb_k=1.96)

    idx = select_batch(pool, scores, k=3, diversity_meta=meta)
    assert len(idx) == 3
    assert all(0 <= j < len(pool) for j in idx)
