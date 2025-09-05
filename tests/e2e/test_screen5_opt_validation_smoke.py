from services.opt_validation import evaluate_hitl_level, summarize_for_trace, require_ack

def test_opt_validation_smoke_paths():
    # OK path
    level_ok, msgs_ok = evaluate_hitl_level(
        metrics={"candidate_count": 200, "selected_count": 8, "safety_blocked": 20, "novelty_blocked": 10, "diversity_min": 0.4, "approx_uncertain_frac": 0.2},
        requested_batch=8,
    )
    assert level_ok == 0
    assert require_ack(level_ok) is False

    # Risky path
    level_risk, msgs_risk = evaluate_hitl_level(
        metrics={"candidate_count": 64, "selected_count": 2, "safety_blocked": 20, "novelty_blocked": 12, "diversity_min": 0.08, "approx_uncertain_frac": 0.7},
        requested_batch=8,
    )
    assert level_risk >= 2
    assert require_ack(level_risk) is True

    trace = summarize_for_trace(level_risk, {"candidate_count": 64, "selected_count": 2, "safety_blocked": 20, "novelty_blocked": 12, "diversity_min": 0.08, "approx_uncertain_frac": 0.7})
    assert trace["hitl_level"] == level_risk
