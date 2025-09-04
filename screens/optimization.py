# screens/optimization.py
# ============================================================
# Screen 5 — Optimization & Next Runs (Thin Screen)
# ============================================================

from __future__ import annotations
import os, sys, json, time, io
from typing import Any, Dict, List, Tuple
from pathlib import Path

# ---- Always expose `st` at module level (real or stub) ----
try:
    import streamlit as st  # type: ignore
except Exception:
    class _StStub:
        session_state: dict = {}
        def __getattr__(self, _name):
            def _noop(*_a, **_k):  # pragma: no cover
                return None
            return _noop
    st = _StStub()  # type: ignore

import numpy as np
import pandas as pd

from utils.runtime import env_flag, session_slug, now_utc_iso
from utils.uilog import write_event_jsonl  # shared JSONL writer
from utils.screenlog import screen_log  # canonical JSONL logger used across screens
from ui.blocks import nav_bar  # canonical nav

from services import opt_constraints as s5c
from services import opt_candidate_pool as s5p
from services import opt_scoring as s5s
from services import opt_guardrails as s5g
from services import opt_validation as s5v
from services import opt_registry as s5r

try:
    from services import artifacts as art
except Exception:  # pragma: no cover
    art = None

try:
    from utils.headless import ensure_s5_min_artifacts  # optional
except Exception:  # pragma: no cover
    ensure_s5_min_artifacts = None  # type: ignore

ARTIFACTS_DIR = Path("artifacts")

# ---------------------------
# Demo-only helpers (kept local by design)
# ---------------------------
def _demo_model_fallback():
    class _Demo:
        def predict(self, X):
            out = []
            for row in X:
                x = row.get("X", row.get("x", 0.0))
                try:
                    out.append(float(x) * 2.0 + 1.0)
                except Exception:
                    out.append(1.0)
            return out
    return _Demo()

def _write_json(payload: dict, fname: str):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    if art and hasattr(art, "write_json"):
        art.write_json(payload, fname)  # type: ignore[attr-defined]
        return
    if art and hasattr(art, "save_json"):
        art.save_json(payload, fname)   # type: ignore[attr-defined]
        return
    (ARTIFACTS_DIR / fname).write_text(json.dumps(payload, indent=2), encoding="utf-8")

def _write_df(df: pd.DataFrame, fname: str):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    if art and hasattr(art, "write_dataframe"):
        art.write_dataframe(df, fname)  # type: ignore[attr-defined]
        return
    if art and hasattr(art, "save_csv"):
        art.save_csv(df, fname)         # type: ignore[attr-defined]
        return
    df.to_csv(ARTIFACTS_DIR / fname, index=False)

def _append_log(slug: str, entry: dict) -> None:
    """
    Centralized JSONL logging via utils.uilog.
    Keeps file layout consistent across screens and avoids duplicate writers.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    p = ARTIFACTS_DIR / slug / f"{slug}_screen5_log.jsonl"
    # Delegate to shared writer (append-only JSONL)
    write_event_jsonl(str(p), entry)

def _synthetic_profile() -> dict:
    return {
        "columns_profile": [
            {"column": "X", "dtype": "float64", "n_unique": 25, "value_classification": "normal"},
            {"column": "CAT", "dtype": "object", "n_unique": 2, "value_classification": "normal", "example_values": ["A", "B"]},
        ]
    }

def _synthetic_champion() -> dict:
    return {
        "settings": {"response_col": "Y", "features": ["X"]},
        "model_signature": {"type": "DemoModel", "params": {"enable_categorical": False}},
    }

# ---------------------------
# Core pure pipeline
# ---------------------------
def _single_pass(*, slug: str, profile: dict | None, champion_bundle: dict | None,
                 model_obj: Any, training_preview: List[dict], batch_size: int,
                 acquisition: str, ucb_k: float, uncertainty_mode: str,
                 safety_k: float, novelty_eps: float, seed_val: int
                 ) -> Tuple[Dict[str, Any], Dict[str, Any], pd.DataFrame, Dict[str, Any]]:
    t0 = time.time()

    acq_for_scoring = "EI" if str(acquisition).upper() == "QEI" else str(acquisition).upper()

    space = s5c.infer_space_from_roles(
        profile or {"columns_profile": []},
        champion_bundle or {"settings": {}, "model_signature": {}},
    )

    numeric_constraints: Dict[str, Dict[str, Any]] = {}
    for f, spec in (space.get("numeric") or {}).items():
        low, high = spec.get("low"), spec.get("high")
        if low is None and high is None:
            low, high = 0.0, 1.0
        numeric_constraints[f] = {"low": low, "high": high, "step": spec.get("step"), "lock": False}

    categorical_constraints: Dict[str, Dict[str, Any]] = {}
    for f, spec in (space.get("categorical") or {}).items():
        categorical_constraints[f] = {"allowed": spec.get("allowed"), "lock": False}

    constraints_in = {"numeric": numeric_constraints, "categorical": categorical_constraints}

    norm = s5c.validate_constraints(space, constraints_in)
    pruned = s5c.apply_constraints(space, norm)
    s5c.encode_for_model(pruned, champion_bundle or {"settings": {}, "model_signature": {}})

    n_pool = max(128, int(batch_size) * 20)
    pool = s5p.build_pool(pruned, n_pool=n_pool, seed=int(seed_val))

    mu, sigma = s5s.predict_mu_sigma(model_obj, pool, mode=str(uncertainty_mode))
    y_best = float(np.max(mu)) - 1e-6
    scores = s5s.score_acquisition(acq_for_scoring, mu, sigma, y_best, ucb_k=float(ucb_k))

    keep_safety, safety_blocked = s5g.apply_safety_filter(
        mu, sigma, k=float(safety_k),
        mode=("deterministic" if str(uncertainty_mode) == "deterministic" else "approx"),
        abs_limits=None,
    )
    diversity_meta = {"numeric": pruned.get("numeric", {}), "categorical": pruned.get("categorical", {})}
    keep_novel, novelty_blocked = s5g.apply_novelty_filter(pool, training_preview, eps=float(novelty_eps), meta=diversity_meta)
    keep_mask = keep_safety & keep_novel

    if not np.any(keep_mask):
        metrics = s5g.build_metrics_dict(
            candidate_count=len(pool), selected_idx=[],
            safety_blocked=int(safety_blocked), novelty_blocked=int(novelty_blocked),
            diversity_min=None, approx_uncertain_frac=0.0
        )
        level, msgs = s5v.evaluate_hitl_level(metrics, requested_batch=int(batch_size))
        raise RuntimeError("HITL L4: infeasible — " + " ".join(msgs))

    kept = np.where(keep_mask)[0]
    sel_idx = s5s.select_batch([pool[i] for i in kept], scores[kept], k=int(batch_size), diversity_meta=diversity_meta)
    final_idx = [int(kept[i]) for i in sel_idx]

    diversity_min = s5g.summarize_diversity(pool, final_idx, meta=diversity_meta)
    sigma_hi = float(np.quantile(sigma[keep_mask], 0.75)) if np.any(keep_mask) else 0.0
    approx_uncertain_frac = s5g.compute_uncertain_fraction(sigma[final_idx], sigma_hi=sigma_hi)

    metrics = s5g.build_metrics_dict(
        candidate_count=len(pool), selected_idx=final_idx,
        safety_blocked=int(safety_blocked), novelty_blocked=int(novelty_blocked),
        diversity_min=diversity_min, approx_uncertain_frac=approx_uncertain_frac
    )
    level, messages = s5v.evaluate_hitl_level(metrics, requested_batch=int(batch_size))
    ack_required = s5v.require_ack(level)
    ack_record = s5v.build_ack_record(level, messages, operator=None)

    rows = []
    for j in final_idx:
        r = dict(pool[j])
        r["_mu"] = float(mu[j]); r["_sigma"] = float(sigma[j]); r["_score"] = float(scores[j])
        rows.append(r)
    df = pd.DataFrame(rows)

    settings_payload = {
        "schema_version": "1.2",
        "batch_size": int(batch_size),
        "acquisition": str(acquisition),
        "acquisition_for_scoring": acq_for_scoring,
        "ucb_k": float(ucb_k),
        "seed": int(seed_val),
        "uncertainty_mode": str(uncertainty_mode),
        "constraints": norm,
        "guardrails": {"safety_k": float(safety_k), "novelty_eps": float(novelty_eps), "sigma_hi": sigma_hi},
        "timestamp_utc": now_utc_iso(),
    }
    trace_payload = {
        "schema_version": "1.1",
        "candidate_count": int(len(pool)),
        "diversity_kept": int(len(final_idx)),
        "safety_blocked": int(safety_blocked),
        "novelty_blocked": int(novelty_blocked),
        "diversity_min": diversity_min,
        "approx_uncertain_frac": approx_uncertain_frac,
        "hitl_level": int(level),
        "hitl_messages": list(messages),
        "runtime_sec": float(time.time() - t0),
        "timestamp_utc": now_utc_iso(),
        "ack": ack_record,
    }
    hitl_info = {"level": level, "ack_required": ack_required, "messages": messages}
    return settings_payload, trace_payload, df, hitl_info

# ---------------------------
# Headless autorun with full fallback ladder
# ---------------------------
def _headless_autorun():
    slug = session_slug()

    ui_defaults = {
        "batch_size": 8, "acquisition": "qEI", "ucb_k": 1.96,
        "uncertainty_mode": "approx_rf", "safety_k": 2.0,
        "novelty_eps": 0.05, "seed": 1729,
    }

    normalized, _ = s5r.normalize_settings({
        "batch_size": ui_defaults["batch_size"],
        "acquisition": ui_defaults["acquisition"],
        "ucb_k": ui_defaults["ucb_k"],
        "uncertainty_mode": ui_defaults["uncertainty_mode"],
        "seed": ui_defaults["seed"],
    })

    profile = None
    champion_bundle = None
    training_preview: List[dict] = []
    model_obj: Any = None

    try:
        if os.environ.get("DOE_WIZARD_PROFILE_JSON"):
            profile = json.loads(os.environ["DOE_WIZARD_PROFILE_JSON"])
        if os.environ.get("DOE_WIZARD_CHAMPION_JSON"):
            champion_bundle = json.loads(os.environ["DOE_WIZARD_CHAMPION_JSON"])
        if os.environ.get("DOE_WIZARD_TRAINING_PREVIEW_JSON"):
            training_preview = json.loads(os.environ["DOE_WIZARD_TRAINING_PREVIEW_JSON"])
    except Exception:
        pass

    try:
        slug = st.session_state.get("session_slug", slug)
        profile = st.session_state.get("session_profile", profile)
        champion_bundle = st.session_state.get("champion_bundle", champion_bundle)
        training_preview = st.session_state.get("s5_training_preview", training_preview) or []
        model_obj = st.session_state.get("s5_demo_model", model_obj)
    except Exception:
        pass

    if profile is None or not isinstance(profile, dict) or not profile.get("columns_profile"):
        profile = _synthetic_profile()
    if champion_bundle is None or not isinstance(champion_bundle, dict) or not champion_bundle.get("settings"):
        champion_bundle = _synthetic_champion()
    if model_obj is None:
        model_obj = _demo_model_fallback()

    ladder_step = "normal"

    try:
        settings, trace, df, hitl = _single_pass(
            slug=slug, profile=profile, champion_bundle=champion_bundle, model_obj=model_obj,
            training_preview=training_preview, batch_size=normalized["batch_size"],
            acquisition=normalized["acquisition"], ucb_k=normalized["ucb_k"],
            uncertainty_mode=normalized["uncertainty_mode"], safety_k=ui_defaults["safety_k"],
            novelty_eps=ui_defaults["novelty_eps"], seed_val=normalized["seed"],
        )
    except Exception as e1:
        msg = str(e1).lower()
        if "empty batch" in msg or "empty feasible set" in msg or "infeasible" in msg:
            ladder_step = "relaxed_guardrails"
            try:
                settings, trace, df, hitl = _single_pass(
                    slug=slug, profile=profile, champion_bundle=champion_bundle, model_obj=model_obj,
                    training_preview=[],  # drop novelty reference
                    batch_size=normalized["batch_size"], acquisition=normalized["acquisition"],
                    ucb_k=normalized["ucb_k"], uncertainty_mode=normalized["uncertainty_mode"],
                    safety_k=0.0, novelty_eps=0.0, seed_val=normalized["seed"],
                )
            except Exception:
                # Step 3: last-resort selection without guardrails; constraints only
                ladder_step = "no_guardrails_topk"
                space = s5c.infer_space_from_roles(profile, champion_bundle)
                # seed constraints
                numeric_constraints, categorical_constraints = {}, {}
                for f, spec in (space.get("numeric") or {}).items():
                    low, high = spec.get("low"), spec.get("high")
                    if low is None and high is None:
                        low, high = 0.0, 1.0
                    numeric_constraints[f] = {"low": low, "high": high, "step": spec.get("step"), "lock": False}
                for f, spec in (space.get("categorical") or {}).items():
                    categorical_constraints[f] = {"allowed": spec.get("allowed"), "lock": False}
                constraints_in = {"numeric": numeric_constraints, "categorical": categorical_constraints}
                norm = s5c.validate_constraints(space, constraints_in)
                pruned = s5c.apply_constraints(space, norm)
                s5c.encode_for_model(pruned, champion_bundle)
                n_pool = max(128, int(normalized["batch_size"]) * 20)
                pool = s5p.build_pool(pruned, n_pool=n_pool, seed=int(normalized["seed"]))
                mu, sigma = s5s.predict_mu_sigma(model_obj, pool, mode=str(normalized["uncertainty_mode"]))
                y_best = float(np.max(mu)) - 1e-6
                acq_for_scoring = "EI" if str(normalized["acquisition"]).upper() == "QEI" else str(normalized["acquisition"]).upper()
                scores = s5s.score_acquisition(acq_for_scoring, mu, sigma, y_best, ucb_k=float(normalized["ucb_k"]))
                order = np.argsort(-scores)[: int(normalized["batch_size"])]
                rows = []
                for j in order:
                    r = dict(pool[int(j)])
                    r["_mu"] = float(mu[int(j)]); r["_sigma"] = float(sigma[int(j)]); r["_score"] = float(scores[int(j)])
                    rows.append(r)
                # Ensure non-empty CSV: header if no rows
                df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=list((pool[0] if pool else {}).keys()) + ["_mu","_sigma","_score"])
                diversity_meta = {"numeric": pruned.get("numeric", {}), "categorical": pruned.get("categorical", {})}
                diversity_min = s5g.summarize_diversity(pool, list(map(int, order)), meta=diversity_meta) if len(order) else None
                sigma_hi = float(np.quantile(sigma, 0.75)) if len(sigma) else 0.0
                approx_uncertain_frac = s5g.compute_uncertain_fraction(sigma[order], sigma_hi=sigma_hi) if len(order) else 0.0
                settings = {
                    "schema_version": "1.2",
                    "batch_size": int(normalized["batch_size"]),
                    "acquisition": str(normalized["acquisition"]),
                    "acquisition_for_scoring": acq_for_scoring,
                    "ucb_k": float(normalized["ucb_k"]),
                    "seed": int(normalized["seed"]),
                    "uncertainty_mode": str(normalized["uncertainty_mode"]),
                    "constraints": norm,
                    "guardrails": {"safety_k": ui_defaults["safety_k"], "novelty_eps": ui_defaults["novelty_eps"], "sigma_hi": sigma_hi},
                    "timestamp_utc": now_utc_iso(),
                }
                trace = {
                    "schema_version": "1.1",
                    "candidate_count": int(len(pool)),
                    "diversity_kept": int(len(order)),
                    "safety_blocked": 0,
                    "novelty_blocked": 0,
                    "diversity_min": diversity_min,
                    "approx_uncertain_frac": approx_uncertain_frac,
                    "hitl_level": 0,
                    "hitl_messages": ["Fallback: guardrails bypassed for headless artifact creation."],
                    "runtime_sec": 0.0,
                    "timestamp_utc": now_utc_iso(),
                    "ack": {"level": 0, "messages": ["Fallback path"], "operator": None, "ack_ts": None},
                }
                hitl = {"level": 0, "ack_required": False, "messages": ["fallback_no_guardrails"]}

    if os.environ.get("DOE_WIZARD_S5_AUTOACK", "").strip() == "1" and isinstance(trace.get("ack"), dict):
        trace["ack"]["ack_ts"] = now_utc_iso()

    settings_path = ARTIFACTS_DIR / slug / "optimization_settings.json"
    proposals_path = ARTIFACTS_DIR / slug / "proposals.csv"
    trace_path = ARTIFACTS_DIR / slug / "optimization_trace.json"

    _write_json(settings, f"{slug}/optimization_settings.json")
    _write_df(df, f"{slug}/proposals.csv")
    _write_json(trace, f"{slug}/optimization_trace.json")

    try:
        screen_log(slug, "s5", {"event": "write", "artifact": settings_path.name, "path": str(settings_path), "ts": now_utc_iso()})
        screen_log(slug, "s5", {"event": "write", "artifact": proposals_path.name, "path": str(proposals_path), "ts": now_utc_iso()})
        screen_log(slug, "s5", {"event": "write", "artifact": trace_path.name, "path": str(trace_path), "ts": now_utc_iso()})
    except Exception:
        pass

    _append_log(slug, {
        "slug": slug, "event": "screen5_run_headless",
        "ladder_step": ladder_step,
        "batch_size": settings["batch_size"],
        "acquisition": settings["acquisition"],
        "acquisition_for_scoring": settings.get("acquisition_for_scoring"),
        "uncertainty_mode": settings["uncertainty_mode"],
        "guardrails": settings["guardrails"],
        "hitl_level": int(trace.get("hitl_level", 0)),
        "ts": now_utc_iso(),
    })

# ---------------------------
# Minimal UI wrapper + nav (aligned to docs/state_and_artifacts.md)
# ---------------------------
def _s5_ready(slug: str) -> bool:
    """Gate Next on presence of proposals.csv and optimization_settings.json for the slug."""
    if not slug:
        return False
    has_props = (ARTIFACTS_DIR / slug / "proposals.csv").exists()
    has_settings = (ARTIFACTS_DIR / slug / "optimization_settings.json").exists()
    return bool(has_props and has_settings)


def render(slug: str | None = None) -> None:
    """Thin Screen 5 UI shell to expose canonical nav bar without mutating existing pipeline.

    Back: enabled; Reset: logs + reruns; Next: enabled when proposals/settings exist (autosave gate).
    """
    title = "Screen 5 — Optimization & Next Runs"
    try:
        st.title(title)
    except Exception:
        # If not under Streamlit, do nothing
        return

    # Resolve slug from session state or runtime helper
    if slug is None:
        try:
            slug = st.session_state.get("session_slug") if "session_slug" in st.session_state else session_slug()
        except Exception:
            slug = session_slug()

    # Entry log
    try:
        screen_log(slug or "unknown", "s5", {"event": "enter", "ts": now_utc_iso()})
    except Exception:
        pass

    # Canonical nav bar (Back / Reset / Next)
    st.divider()
    back_clicked, reset_clicked, next_clicked = nav_bar(
        back_enabled=True,
        next_enabled=_s5_ready(slug or ""),
        on_next_label="Next \u2192",
    )

    if back_clicked:
        # Router would navigate to Screen 4 in the full app
        pass

    if reset_clicked:
        # Log reset for audit; keep artifacts intact (no destructive deletes)
        screen_log(slug or "unknown", "screen5", {"event": "nav_reset"})
        # No S5-specific session keys to clear in this thin shell; simply rerun
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    if next_clicked:
        # Align to spec: autosave already happened during optimization; just log nav
        screen_log(slug or "unknown", "screen5", {"event": "nav_next"})
        # Router would proceed to Screen 6

# ---------------------------
# Runtime detection helpers
# ---------------------------
def _running_in_streamlit() -> bool:
    """True when executed under `streamlit run`."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx  # type: ignore
        return get_script_run_ctx() is not None
    except Exception:
        return False

# ---------------------------
# Module import behavior
# ---------------------------
if env_flag("DOE_WIZARD_S5_AUTORUN"):
    try:
        if ensure_s5_min_artifacts is not None:
            ensure_s5_min_artifacts(session_slug())
        _headless_autorun()
    except Exception as e:
        _append_log(session_slug(), {
            "slug": session_slug(),
            "event": "screen5_run_headless_error",
            "error": str(e),
            "ts": now_utc_iso(),
        })
elif _running_in_streamlit():
    # Only run UI when actually inside `streamlit run`
    st.title("Screen 5 — Optimization")
    slug = st.session_state.get("session_slug", session_slug())
    st.caption(f"Session: {slug}")

    profile = st.session_state.get("session_profile", None)
    champion_bundle = st.session_state.get("champion_bundle", None)
    demo_model = st.session_state.get("s5_demo_model", None)
    training_preview = st.session_state.get("s5_training_preview", []) or []

    batch_default, ucb_k_default, seed_default = 8, 1.96, 1729
    safety_k_default, novelty_eps_default = 2.0, 0.05

    c1, c2, c3, c4 = st.columns(4)
    batch_size = c1.number_input("Batch size", 1, 64, batch_default)
    acquisition = c2.selectbox("Acquisition", ["qEI", "EI", "UCB", "PI"], index=0)
    ucb_k = c3.number_input("UCB k", 0.0, 10.0, ucb_k_default, step=0.1, format="%.2f")
    uncertainty_mode = c4.selectbox("Uncertainty mode", ["native", "approx_rf", "deterministic"], index=1)

    c5, c6, c7 = st.columns(3)
    safety_k = c5.number_input("Safety: k (μ±kσ)", 0.0, 10.0, safety_k_default, step=0.1, format="%.2f")
    novelty_eps = c6.number_input("Novelty: ε_data", 0.0, 1.0, novelty_eps_default, step=0.01, format="%.2f")
    seed_val = c7.number_input("Random seed", value=seed_default, step=1)

    if st.button("Run Optimization", type="primary"):
        try:
            normalized, warns = s5r.normalize_settings({
                "batch_size": int(batch_size),
                "acquisition": str(acquisition),
                "ucb_k": float(ucb_k),
                "uncertainty_mode": str(uncertainty_mode),
                "seed": int(seed_val),
            })
            for w in (warns or []):
                st.info(w)

            model_obj = demo_model or _demo_model_fallback()
            settings, trace, df, hitl = _single_pass(
                slug=slug, profile=profile, champion_bundle=champion_bundle, model_obj=model_obj,
                training_preview=training_preview,
                batch_size=normalized["batch_size"], acquisition=normalized["acquisition"],
                ucb_k=normalized["ucb_k"], uncertainty_mode=normalized["uncertainty_mode"],
                safety_k=float(safety_k), novelty_eps=float(novelty_eps), seed_val=normalized["seed"],
            )
            st.success(f"Selected {len(df)} proposals. HITL level = {hitl['level']}.")
            st.dataframe(df)
        except Exception as e:
            st.error(str(e))
else:
    # Imported as a module (tests, CLI import, etc.) — do nothing
    pass
