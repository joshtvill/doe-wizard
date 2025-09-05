# screens/modeling.py
"""
SCREEN 4 :: Modeling & Evaluation (thin shell)
- No function definitions (per file hygiene).
- Orchestrates services: modeling_train, modeling_select, artifacts.
"""

import os
import glob
from datetime import datetime
import pandas as pd
import streamlit as st

from services.modeling_train import train_models
from services.modeling_select import select_champion, build_champion_bundle
from services.artifacts import save_csv, save_json
from utils.screenlog import screen_log  # NEW
from utils.time import now_utc_iso
from state import autoload_latest_artifacts, fingerprint_check
from ui.blocks import nav_bar  # Canonical nav

# Optional session slug from state if available
try:
    import state as app_state  # repo-local helper if present
    _DEFAULT_SLUG = getattr(app_state, "get_session_slug", lambda: "dev_session")()
except Exception:
    _DEFAULT_SLUG = "dev_session"

st.title("Screen 4 — Modeling & Evaluation")

# Entry log
try:
    slug_for_log = (st.session_state.get("session_slug") if "session_slug" in st.session_state else None) or _DEFAULT_SLUG
    screen_log(slug_for_log, "s4", {"event": "enter", "ts": now_utc_iso()})
except Exception:
    pass
# Autoload + fingerprint guard
try:
    meta = autoload_latest_artifacts(slug_for_log)
    chk = fingerprint_check(meta.get("upstream", {}), meta.get("current", {}))
    if not chk["ok"]:
        screen_log(slug_for_log, "s4", {"event": "fingerprint_mismatch", "reasons": chk["reasons"], "ts": now_utc_iso()})
        st.warning("Artifacts appear stale for this screen. Recompute or proceed with stale outputs (not recommended).")
        c1, c2 = st.columns(2)
        if c1.button("Recompute upstream"):
            try:
                from pathlib import Path
                from services.modeling_train import recompute_modeling
                modeling_ready = meta["paths"].get("modeling_ready") or (Path("artifacts") / slug_for_log / "modeling_ready.csv")
                results = recompute_modeling(slug_for_log, str(modeling_ready))
                for item in results.get("written", []):
                    screen_log(slug_for_log, "s4", {"event": "write", "artifact": item["artifact"], "path": item["path"], "ts": now_utc_iso()})
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Recompute failed: {e}")
        if not c2.button("Proceed with stale"):
            st.stop()
    else:
        screen_log(slug_for_log, "s4", {"event": "autoload", "ts": now_utc_iso()})
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# 1) Dataset selection
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("1) Choose dataset")

art_paths = []
if os.path.isdir("artifacts"):
    art_paths.extend(glob.glob(os.path.join("artifacts", "*_modeling_ready.csv")))
    art_paths.extend(glob.glob(os.path.join("artifacts", "*_collapsed.csv")))
art_paths = sorted(set(art_paths))

ds_path = st.selectbox(
    "Pick an artifacts CSV (prefer *_modeling_ready.csv; fallback to *_collapsed.csv):",
    options=["— select —"] + art_paths,
    index=0,
    key="s4_ds_path",
)

df = None
if ds_path and ds_path != "— select —":
    try:
        df = pd.read_csv(ds_path)
        st.caption(f"Loaded: {ds_path} · shape={df.shape}")
        st.dataframe(df.head(20), use_container_width=True)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# 2) Modeling controls (response + validation + models)
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("2) Configure modeling")

numeric_cols = []
if df is not None:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

resp_col = st.selectbox(
    "Response column",
    options=["— select —"] + numeric_cols,
    index=(len(numeric_cols)) if False else 0,
    key="s4_resp",
)

val_strategy = st.radio(
    "Validation strategy",
    options=["kfold", "holdout", "groupkfold"],
    index=0,
    horizontal=True,
    key="s4_val_strategy",
)

col1, col2, col3 = st.columns(3)
with col1:
    k_splits = st.number_input("K (for kfold/groupkfold)", min_value=2, max_value=10, value=5, step=1, key="s4_k")
with col2:
    test_size = st.slider("Holdout test_size", min_value=0.1, max_value=0.5, value=0.2, step=0.05, key="s4_testsize")
with col3:
    seed = st.number_input("Random seed", min_value=0, max_value=10_000_000, value=1729, step=1, key="s4_seed")

group_key = None
if df is not None and val_strategy == "groupkfold":
    other_cols = [c for c in df.columns if c != resp_col]
    group_key = st.selectbox("Group key (required for GroupKFold)", options=["— select —"] + other_cols, key="s4_groupkey")
    if group_key == "— select —":
        group_key = None

st.caption("Select models to train")
c1, c2, c3 = st.columns(3)
with c1:
    use_rf = st.checkbox("Random Forest (RF)", value=True, key="s4_use_rf")
with c2:
    use_xgb = st.checkbox("XGBoost (XGB)", value=True, key="s4_use_xgb")
with c3:
    use_gpr = st.checkbox("Gaussian Process (GPR)", value=True, key="s4_use_gpr")

opt_col1, opt_col2 = st.columns(2)
with opt_col1:
    gpr_cap = st.number_input("GPR max rows (skip if > cap)", min_value=100, max_value=50000, value=8000, step=100, key="s4_gpr_cap")
with opt_col2:
    save_pickle = st.checkbox("Include champion .pkl on Save (optional)", value=False, key="s4_save_pkl")
    if save_pickle:
        st.info("Note: Pickle write is handled by Screen 4 save step (not in this module).")

# ──────────────────────────────────────────────────────────────────────────────
# 3) Execute training
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("3) Execute")

exec_disabled = not (df is not None and resp_col in numeric_cols and any([use_rf, use_xgb, use_gpr]))
if val_strategy == "groupkfold" and group_key is None:
    exec_disabled = True

if st.button("Execute training", type="primary", disabled=exec_disabled, key="s4_btn_execute"):
    try:
        validation = {"strategy": val_strategy, "k": k_splits, "test_size": float(test_size), "group_key": group_key}
        choices = {"rf": use_rf, "xgb": use_xgb, "gpr": use_gpr}

        bundle = train_models(
            df=df,
            response_col=resp_col,
            validation=validation,
            model_choices=choices,
            seed=int(seed),
            gpr_max_rows=int(gpr_cap),
        )

        st.session_state["s4_compare"] = bundle["compare"]
        st.session_state["s4_settings"] = bundle["settings"]
        st.session_state["s4_fitted"] = bundle["fitted"]

        # NEW: JSONL event
        screen_log(_DEFAULT_SLUG, "screen4", {
            "event": "execute",
            "resp_col": resp_col,
            "val_strategy": val_strategy,
            "models": {k: v for k, v in choices.items()},
            "rows": int(df.shape[0]) if df is not None else None,
            "cols": int(df.shape[1]) if df is not None else None,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

        st.success("Training complete.")
    except Exception as e:
        st.error(f"Training failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# 4) Results & champion
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("4) Results")

if "s4_compare" in st.session_state:
    cmp_df = st.session_state["s4_compare"]
    st.dataframe(cmp_df, use_container_width=True)

    sel = select_champion(cmp_df, min_r2=None)
    st.session_state["s4_champion"] = sel

    with st.expander("Champion selection details", expanded=True):
        st.markdown(f"**Champion:** `{sel['champion_id']}`")
        st.write({k: v for k, v in sel["champion_row"].items() if k in ("model", "r2_mean", "rmse_mean", "mae_mean", "fit_seconds_full", "notes")})
        if sel["rationale"]:
            st.markdown("**Rationale**")
            for line in sel["rationale"]:
                st.write("- " + line)
        if sel["warnings"]:
            st.warning(" | ".join(sel["warnings"]))

# ──────────────────────────────────────────────────────────────────────────────
# 5) Save artifacts
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("5) Save")

slug = st.text_input("Session slug", value=_DEFAULT_SLUG, key="s4_slug")
save_disabled = not all(k in st.session_state for k in ["s4_compare", "s4_settings", "s4_fitted", "s4_champion"])

# Show intended basenames (not full paths). services.artifacts will place them under artifacts/
compare_name = f"{slug}_model_compare.csv"
bundle_name = f"{slug}_champion_bundle.json"
st.caption(f"Files to be written under artifacts/: {compare_name}, {bundle_name}")

if st.button("Save artifacts", disabled=save_disabled, key="s4_btn_save"):
    try:
        cmp_df = st.session_state["s4_compare"]
        settings = st.session_state["s4_settings"]
        fitted = st.session_state["s4_fitted"]
        sel = st.session_state["s4_champion"]
        champ_id = sel["champion_id"]

        pack = build_champion_bundle(
            settings=settings,
            compare_df=cmp_df,
            fitted=fitted,
            champion_id=champ_id,
            include_pickle=bool(save_pickle),
        )

        written_compare = save_csv(cmp_df, compare_name)
        # Attach fingerprints if available
        try:
            meta = autoload_latest_artifacts(slug)
            up = meta.get("upstream", {})
            pack = dict(pack)
            if up.get("dataset_hash"): pack["dataset_hash"] = up["dataset_hash"]
            if up.get("roles_signature"): pack["roles_signature"] = up["roles_signature"]
            pack.setdefault("schema_version", "2025-08-29")
        except Exception:
            pass
        written_bundle = save_json(pack, bundle_name)

        # Write events (canonical)
        try:
            from pathlib import Path as _P
            screen_log(slug, "s4", {"event": "write", "artifact": _P(written_compare).name, "path": str(written_compare), "ts": now_utc_iso()})
            screen_log(slug, "s4", {"event": "write", "artifact": _P(written_bundle).name, "path": str(written_bundle), "ts": now_utc_iso()})
        except Exception:
            pass

        # NEW: JSONL event
        screen_log(slug, "screen4", {
            "event": "save",
            "compare": written_compare,
            "bundle": written_bundle,
            "champion_id": champ_id,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

        st.success("Artifacts saved.")
        st.caption(f"Compare: {written_compare}")
        st.caption(f"Bundle: {written_bundle}")

        if save_pickle:
            st.info("Pickle save is not implemented yet in this screen. (Intentionally off for MVP.)")
    except Exception as e:
        st.error(f"Save failed: {e}")

# --- Canonical nav bar (Back / Reset / Next) ---
st.divider()
back_clicked, reset_clicked, next_clicked = nav_bar(
    back_enabled=True,
    next_enabled=bool(
        all(k in st.session_state for k in ["s4_compare", "s4_settings", "s4_fitted", "s4_champion"])
    ),
    on_next_label="Next \u2192",
)

if back_clicked:
    # Router would navigate to Screen 3 in full app
    pass

if reset_clicked:
    # Log and clear known S4 state keys, then rerun
    screen_log(_DEFAULT_SLUG, "screen4", {"event": "nav_reset"})
    for k in list(st.session_state.keys()):
        if k.startswith("s4_"):
            try:
                del st.session_state[k]
            except Exception:
                pass
    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

if next_clicked:
    screen_log(_DEFAULT_SLUG, "screen4", {"event": "nav_next"})
    # Router would advance to Screen 5 here
