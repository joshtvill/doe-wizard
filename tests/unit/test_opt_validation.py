import pytest

from services.opt_validation import (
    evaluate_hitl_level,
    require_ack,
    build_ack_record,
    summarize_for_trace,
    default_thresholds,
)

def test_default_thresholds():
    t = default_thresholds()
    assert t["MIN_SELECTED_OK"] == 1
    assert 0.0 < t["DIVERSITY_EPS"] < 1.0

def test_l4_infeasible_empty_batch():
    level, msgs = evaluate_hitl_level(
        metrics={"candidate_count": 200, "selected_count": 0, "safety_blocked": 0, "novelty_blocked": 0},
        requested_batch=8,
    )
    assert level == 4
    assert any("Empty batch" in m for m in msgs)
    assert require_ack(level) is True  # L4 blocks; ack not sufficient but still "requires" human action

def test_l3_severe_block():
    level, msgs = evaluate_hitl_level(
        metrics={"candidate_count": 100, "selected_count": 8, "safety_blocked": 40, "novelty_blocked": 20},
        requested_batch=8,
    )
    assert level >= 3
    assert any("Severe pruning" in m for m in msgs)
    assert require_ack(level) is True

def test_l2_underfilled_and_uncertain():
    level, msgs = evaluate_hitl_level(
        metrics={"candidate_count": 50, "selected_count": 2, "safety_blocked": 0, "novelty_blocked": 0, "approx_uncertain_frac": 0.8},
        requested_batch=8,
    )
    assert level == 2
    assert any("Underfilled batch" in m for m in msgs)
    assert any("High uncertainty" in m for m in msgs)
    assert require_ack(level) is True

def test_l1_low_diversity_only():
    level, msgs = evaluate_hitl_level(
        metrics={"candidate_count": 64, "selected_count": 8, "safety_blocked": 0, "novelty_blocked": 0, "diversity_min": 0.05},
        requested_batch=8,
    )
    assert level == 1
    assert any("Low diversity" in m for m in msgs)
    assert require_ack(level) is True

def test_l0_ok():
    level, msgs = evaluate_hitl_level(
        metrics={"candidate_count": 256, "selected_count": 8, "safety_blocked": 10, "novelty_blocked": 10, "diversity_min": 0.5, "approx_uncertain_frac": 0.1},
        requested_batch=8,
        thresholds={"BLOCK_RATE_HI": 0.9, "DIVERSITY_EPS": 0.1, "UNCERTAIN_FRAC_HI": 0.9},
    )
    assert level == 0
    assert msgs == []
    assert require_ack(level) is False

def test_ack_record_and_trace_summary():
    level = 2
    msgs = ["Underfilled batch: 3/8 selected.", "High uncertainty: 70% of selected have high σ."]
    ack = build_ack_record(level, msgs, operator="op-1")
    assert ack["ack_required"] is True
    assert ack["level"] == 2
    assert ack["operator"] == "op-1"
    assert ack["ack_ts"] is None

    trace = summarize_for_trace(level, {
        "candidate_count": 120, "selected_count": 6, "safety_blocked": 10, "novelty_blocked": 5,
        "diversity_min": 0.2, "approx_uncertain_frac": 0.4
    })
    assert trace["hitl_level"] == 2
    assert trace["selected_count"] == 6
