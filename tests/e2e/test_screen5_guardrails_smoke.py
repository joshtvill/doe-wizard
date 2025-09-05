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
    "categorical": {"cat": {"allowed": ["A","B"]}},
}

def test_guardrails_smoke_path():
    # Fake pool & training
    pool = [{"x": 0.0, "cat": "A"}, {"x": 0.5, "cat": "B"}, {"x": 1.0, "cat": "A"}, {"x": 1.5, "cat": "B"}]
    training = [{"x": 0.0, "cat": "A"}, {"x": 2.0, "cat": "B"}]

    # Safety (approx mode)
    mu = np.array([0.0, 0.5, 1.0, 1.5])
    sigma = np.array([0.2, 0.2, 0.2, 0.2])
    keep_safety, s_blocked = apply_safety_filter(mu, sigma, k=1.0, mode="approx")

    # Novelty vs training
    keep_novel, n_blocked = apply_novelty_filter(pool, training, eps=0.05, meta=META)

    # Combined keep (AND)
    keep = keep_safety & keep_novel
    kept_idx = [i for i, v in enumerate(keep) if v]

    # Diversity among kept
    div_min = summarize_diversity(pool, kept_idx, meta=META)

    # Uncertainty summary
    ufrac = compute_uncertain_fraction(sigma[keep], sigma_hi=0.25)

    # Metrics assembly
    m = build_metrics_dict(candidate_count=len(pool), selected_idx=kept_idx, safety_blocked=s_blocked, novelty_blocked=n_blocked, diversity_min=div_min, approx_uncertain_frac=ufrac)
    assert m["candidate_count"] == 4
    assert m["selected_count"] == len(kept_idx)
