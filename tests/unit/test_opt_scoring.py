import numpy as np
import pytest

from services.opt_scoring import predict_mu_sigma, score_acquisition, select_batch

# ---- Dummy models for tests ----

class DeterministicModel:
    """predict = linear combo over dict features 'x' and 'bias'"""
    def predict(self, X):
        # X is list[dict]; y = x + bias
        return np.array([row.get("x", 0.0) + row.get("bias", 0.0) for row in X], dtype=float)

class NativeUncertainModel(DeterministicModel):
    """Adds a predictable std for testing 'native' mode."""
    def predict_std(self, X):
        # σ grows with |x| for test determinism
        return np.array([abs(row.get("x", 0.0)) * 0.1 for row in X], dtype=float)

# --------------------------------

def test_predict_mu_sigma_deterministic():
    model = DeterministicModel()
    X = [{"x": 1.0, "bias": 0.5}, {"x": 2.0, "bias": 0.0}]
    mu, sigma = predict_mu_sigma(model, X, mode="deterministic")
    assert np.allclose(mu, [1.5, 2.0])
    assert np.allclose(sigma, [0.0, 0.0])

def test_predict_mu_sigma_native():
    model = NativeUncertainModel()
    X = [{"x": 3.0, "bias": 0.0}, {"x": -1.0, "bias": 0.0}]
    mu, sigma = predict_mu_sigma(model, X, mode="native")
    assert np.allclose(mu, [3.0, -1.0])
    assert np.allclose(sigma, [0.3, 0.1])

def test_predict_mu_sigma_approx():
    model = DeterministicModel()
    X = [{"x": 0.0, "bias": 0.0}, {"x": 10.0, "bias": 0.0}, {"x": -10.0, "bias": 0.0}]
    mu, sigma = predict_mu_sigma(model, X, mode="approx_rf")
    assert mu.shape == (3,) and sigma.shape == (3,)
    assert np.all(sigma >= 0)

def test_score_acquisition_basic():
    mu = np.array([0.0, 1.0, 2.0])
    sigma = np.array([0.0, 0.5, 1.0])
    y_best = 1.0

    ei = score_acquisition("EI", mu, sigma, y_best)
    ucb = score_acquisition("UCB", mu, sigma, y_best, ucb_k=2.0)
    pi = score_acquisition("PI", mu, sigma, y_best)

    assert ei.shape == (3,)
    assert ucb.shape == (3,)
    assert pi.shape == (3,)
    # deterministic point (sigma=0) reduces EI to max(mu - y_best, 0)
    assert np.isclose(ei[0], 0.0)

def test_select_batch_diversity_greedy():
    pool = [
        {"x": 0.0, "cat": "A"}, {"x": 1.0, "cat": "A"}, {"x": 0.5, "cat": "B"},
        {"x": 2.0, "cat": "B"}, {"x": 1.5, "cat": "A"}
    ]
    mu = np.array([0.0, 1.0, 0.5, 2.0, 1.5])
    sigma = np.array([0.1, 0.1, 0.1, 0.1, 0.1])
    scores = mu  # monotone in mu for test
    diversity_meta = {"numeric": {"x": {"low": 0.0, "high": 2.0}}, "categorical": {"cat": {"allowed": ["A","B"]}}}
    idx = select_batch(pool, scores, k=3, diversity_meta=diversity_meta)
    assert len(idx) == 3
    # ensure top-1 is included and others are reasonably spread
    assert idx[0] == int(np.argmax(scores))
