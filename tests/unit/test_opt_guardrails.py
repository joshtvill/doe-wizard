import numpy as np

from services.opt_guardrails import (
    apply_safety_filter,
    apply_novelty_filter,
    summarize_diversity,
    compute_uncertain_fraction,
    build_metrics_dict,
)

META = {
    "numeric": {"x": {"low": 0.0, "high": 2.0}},
    "categorical": {"cat": {"allowed": ["A", "B"]}},
}

def test_safety_filter_probabilistic_band():
    mu = np.array([0.0, 1.0, 2.0])
    sigma = np.array([0.5, 0.1, 0.5])
    keep, blocked = apply_safety_filter(mu, sigma, k=1.0, mode="approx")
    assert keep.shape == (3,)
    assert blocked >= 0
    # The median is 1.0; points with |mu - 1| <= k*sigma survive
    # mu=1.0 always survives; edges depend on sigma
    assert bool(keep[1])  # avoid identity checks with numpy.bool_

def test_safety_filter_deterministic_abs_limits():
    mu = np.array([0.0, 1.0, 2.0, 3.0])
    sigma = np.zeros_like(mu)
    keep, blocked = apply_safety_filter(mu, sigma, k=1.0, mode="deterministic",
                                        abs_limits={"low": 0.5, "high": 2.5})
    assert np.all(keep == np.array([False, True, True, False]))
    assert blocked == 2

def test_novelty_filter_against_training():
    pool = [{"x": 0.0, "cat": "A"}, {"x": 0.5, "cat": "B"}, {"x": 1.0, "cat": "A"}]
    training = [{"x": 0.0, "cat": "A"}]  # first point identical to a training sample
    keep, blocked = apply_novelty_filter(pool, training, eps=0.1, meta=META)
    assert keep.shape == (3,)
    # The first should be blocked for being distance 0 to training
    assert not bool(keep[0])
    assert blocked >= 1

def test_diversity_summary():
    pool = [{"x": 0.0, "cat": "A"}, {"x": 1.0, "cat": "A"}, {"x": 2.0, "cat": "B"}]
    div = summarize_diversity(pool, selected_idx=[0, 2], meta=META)
    assert div is not None
    assert 0.0 <= div <= 1.0

def test_uncertain_fraction_and_metrics():
    sigma = np.array([0.1, 0.5, 1.0, 0.05])
    frac = compute_uncertain_fraction(sigma, sigma_hi=0.5)
    assert 0.0 <= frac <= 1.0
    metrics = build_metrics_dict(candidate_count=100, selected_idx=[1, 2], safety_blocked=3,
                                 novelty_blocked=4, diversity_min=0.2, approx_uncertain_frac=frac)
    assert metrics["candidate_count"] == 100
    assert metrics["selected_count"] == 2
