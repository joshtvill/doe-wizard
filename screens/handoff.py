# screens/handoff.py
"""
Thin Streamlit orchestration for Screen 6 (Handoff):
 - Discovers artifacts for the active session slug
 - Shows HITL acknowledgements and approval capture
 - Invokes services.handoff_packaging to build + write bundle & log

No heavy business logic here; defers to services/*.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

import streamlit as st

from services.handoff_packaging import (
    discover_artifacts,
    summarize,
    compute_fingerprints,
    build_bundle,
    write_outputs,
)

from utils.screenlog import screen_log  # NEW
from utils.runtime import now_utc_iso
from state import autoload_latest_artifacts, fingerprint_check
from ui.blocks import nav_bar  # Canonical nav

ARTIFACTS_DIR = Path("artifacts")  # local-first per project rules
DEFAULT_R2_ACK_THRESHOLD = 0.60    # user confirmed "modifiable" (Checklist #7)

def render():
    st.title("Screen 6 — Handoff")
    # Entry log
    try:
        slug_for_log = st.session_state.get("session_slug") if "session_slug" in st.session_state else None
        screen_log(slug_for_log or "unknown", "s6", {"event": "enter", "ts": now_utc_iso()})
    except Exception:
        pass
    # Autoload + fingerprint guard
    try:
        eff_slug = (st.session_state.get("session_slug") if "session_slug" in st.session_state else None)
        if eff_slug:
            meta = autoload_latest_artifacts(eff_slug)
            chk = fingerprint_check(meta.get("upstream", {}), meta.get("current", {}))
            if not chk["ok"]:
                screen_log(eff_slug, "s6", {"event": "fingerprint_mismatch", "reasons": chk["reasons"], "ts": now_utc_iso()})
                st.warning("Artifacts appear stale for this screen. Recompute or proceed with stale outputs (not recommended).")
                c1, c2 = st.columns(2)
                if c1.button("Recompute upstream"):
                    st.session_state["force_recompute"] = True
                    st.experimental_rerun()
                if not c2.button("Proceed with stale"):
                    st.stop()
            else:
                screen_log(eff_slug, "s6", {"event": "autoload", "ts": now_utc_iso()})
    except Exception:
        pass

    # 1) Resolve active slug (prefer session state, else infer from artifacts directory)
    slug: Optional[str] = st.session_state.get("session_slug") if "session_slug" in st.session_state else None
    if not slug:
        slug = _infer_latest_slug(ARTIFACTS_DIR)

    colA, colB = st.columns([3, 1])
    with colA:
        st.markdown(f"**Active session slug:** `{slug or 'not detected'}`")
    with colB:
        st.button("Refresh", on_click=lambda: None)

    if not slug:
        st.error("No session slug found. Please open Screen 1 or select a session before exporting a handoff bundle.")
        return

    # 2) Discover artifacts & compute summary
    disc = discover_artifacts(slug=slug, artifacts_dir=ARTIFACTS_DIR)
    smry = summarize(slug=slug, inc=disc.included)
    fps  = compute_fingerprints(disc.included)

    # 3) Display discovery results
    with st.expander("Artifacts discovery", expanded=True):
        st.json(disc.included)
        if disc.missing:
            st.warning(f"Missing required artifacts ({len(disc.missing)}): {disc.missing}")

    with st.expander("Summary (preview)"):
        st.json({
            "records": smry.records,
            "features": smry.features,
            "champion_model": smry.champion_model,
            "proposals": smry.proposals,
            "feasibility": smry.feasibility,
            "fingerprints": {"data_hash": fps.data_hash, "model_hash": fps.model_hash}
        })

    # 4) HITL checklist — acknowledgements
    st.subheader("HITL Checklist (required)")

    r2_threshold = st.number_input(
        "R² threshold to acknowledge if champion is below (modifiable)",
        min_value=0.0, max_value=1.0, value=DEFAULT_R2_ACK_THRESHOLD, step=0.01, format="%.2f"
    )
    r2_value = smry.champion_model.get("r2_cv")
    low_r2 = (isinstance(r2_value, (int, float)) and r2_value < r2_threshold)

    a_lineage = st.checkbox("I verified data lineage & schema versions.")
    a_r2      = st.checkbox(f"I acknowledge champion R² ({r2_value if r2_value is not None else 'N/A'}) vs threshold ({r2_threshold:.2f}).", value=low_r2)
    a_feas    = st.checkbox(f"I reviewed optimization feasibility (ladder={smry.feasibility.get('ladder')}).")
    a_dist    = st.checkbox("I reviewed distance-from-data summary (note: MVP placeholder).")
    a_export  = st.checkbox("I approve export of the handoff bundle with the current status (success/partial).")

    # 5) Approvals capture
    st.subheader("Approvals")
    approver_name = st.text_input("Approver name")
    approver_role = st.text_input("Approver role")
    approval_decision = st.selectbox("Decision", ["approve", "reject"], index=0)
    approver_notes = st.text_area("Notes", value="", height=100)

    approvals = []
    if approver_name and approver_role:
        approvals.append({
            "name": approver_name,
            "role": approver_role,
            "timestamp_local": _now_local_iso_for_ui(),
            "decision": approval_decision,
            "notes": approver_notes.strip(),
        })

    # 6) Export action
    st.divider()
    disabled = not (a_lineage and a_r2 and a_feas and a_dist and a_export and approvals)
    if st.button("Export Handoff Bundle", type="primary", disabled=disabled):
        # Gate acknowledgment (final approval)
        try:
            screen_log(slug, "s6", {"event": "gate_ack", "type": "final_approval", "ts": now_utc_iso()})
        except Exception:
            pass
        bundle = build_bundle(
            slug=slug,
            discovery=disc,
            summary=smry,
            fingerprints=fps,
            schema_version="2.0",
            app_version="0.1.0",
            approvals=approvals,
        )
        bundle_path, log_path = write_outputs(slug=slug, artifacts_dir=ARTIFACTS_DIR, bundle=bundle, hitl_notes=approver_notes)

        # NEW: JSONL event
        screen_log(slug, "screen6", {
            "event": "export",
            "bundle_path": str(bundle_path),
            "log_path": str(log_path),
            "approvals": approvals,
            "ack": {
                "lineage": bool(a_lineage),
                "r2": bool(a_r2),
                "feasibility": bool(a_feas),
                "distance": bool(a_dist),
                "export": bool(a_export),
            },
            "ts": datetime.utcnow().isoformat() + "Z",
        })

        st.success("Handoff bundle exported.")
        st.code(str(bundle_path), language="text")
        st.code(str(log_path), language="text")
        st.json(bundle)

        # Canonical write events
        try:
            from pathlib import Path as _P
            screen_log(slug, "s6", {"event": "write", "artifact": _P(bundle_path).name, "path": str(bundle_path), "ts": now_utc_iso()})
            screen_log(slug, "s6", {"event": "write", "artifact": _P(log_path).name, "path": str(log_path), "ts": now_utc_iso()})
        except Exception:
            pass

    # 7) Quick previews (non-blocking niceties)
    with st.expander("Preview: proposals (head)", expanded=False):
        _show_csv_head(disc.included, suffix="_proposals.csv", n=10)
    with st.expander("Preview: model_compare (head)", expanded=False):
        _show_csv_head(disc.included, suffix="_model_compare.csv", n=10)

    # --- Canonical nav bar (Back / Reset / Next) ---
    st.divider()
    back_clicked, reset_clicked, next_clicked = nav_bar(
        back_enabled=True,
        next_enabled=False,
        on_next_label="Next \u2192",
    )

    if back_clicked:
        # Router would navigate to Screen 5 in the full app
        pass

    if reset_clicked:
        # Log reset; clear lightweight local approval widgets/state
        screen_log(slug, "screen6", {"event": "nav_reset"})
        for k in [
            "session_slug",  # allow rediscovery
            # approval widgets
            "r2_threshold", "a_lineage", "a_r2", "a_feas", "a_dist", "a_export",
            "approver_name", "approver_role", "approval_decision", "approver_notes",
        ]:
            if k in st.session_state:
                try:
                    del st.session_state[k]
                except Exception:
                    pass
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

def _infer_latest_slug(artifacts_dir: Path) -> Optional[str]:
    if not artifacts_dir.exists():
        return None
    candidates = sorted(artifacts_dir.glob("*_session_setup.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    name = candidates[0].name
    return name.replace("_session_setup.json", "")

def _now_local_iso_for_ui() -> str:
    from datetime import datetime
    return datetime.now().astimezone().replace(microsecond=0).isoformat()

def _show_csv_head(included: Dict[str, List[str]], suffix: str, n: int = 10) -> None:
    import pandas as pd
    from io import StringIO
    path = None
    for cat, files in included.items():
        for f in files:
            if f.endswith(suffix):
                path = f
                break
        if path:
            break
    if not path:
        st.info(f"No file ending with {suffix} found.")
        return
    try:
        df = pd.read_csv(path)
        st.dataframe(df.head(n))
    except Exception as e:
        st.error(f"Failed to read {path}: {e}")
