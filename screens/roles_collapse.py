# screens/roles_collapse.py
"""
Screen 3 — Roles • Collapse (thin shell, stable post-Execute state)
- Change-sensitive upload parsing (fingerprint) so Save/Next don’t wipe Execute
- Versioned widget keys for reliable Reset (clears uploader + controls)
- No widget-key mutation after instantiation
- Saves do not touch _K_OUT_DF / _K_READY
"""
from __future__ import annotations
from typing import Dict, List, Any
from datetime import datetime
import json
from pathlib import Path

import streamlit as st
import pandas as pd

from ui.blocks import app_header, section_header, status_zone, table_preview, nav_bar
from services.collapse_engine import run_collapse
from services.file_io import read_csv_lite
from services.artifacts import save_csv, save_json
from utils.ui_state import bump_version, clear_keys
from utils.screenlog import screen_log  # NEW
from utils.time import now_utc_iso
from state import autoload_latest_artifacts, fingerprint_check

# ---- Screen-local state keys (NOT widget keys) ----
_K_VER       = "s3_ver"            # widget version for reset
_K_SRC_DF    = "s3_src_df"
_K_SRC_FP    = "s3_src_fp"         # fingerprint of uploaded file (name:size)
_K_RULES     = "s3_rule_map"       # dict: col -> rule name
_K_OUT_DF    = "s3_out_df"
_K_READY     = "s3_ready_for_next"

# ---- Widget key factories (widget keys change with version) ----
def W_SRC(ver:int) -> str: return f"s3_src_uploader_v{ver}"
def W_GROUPS(ver:int) -> str: return f"s3_groups_multiselect_v{ver}"
def W_RULE(col:str, ver:int) -> str: return f"s3_rule_{col}_v{ver}"

_RULES = ["avg", "min", "max", "last"]

def _init():
    if _K_VER   not in st.session_state: st.session_state[_K_VER]   = 0
    if _K_SRC_DF not in st.session_state: st.session_state[_K_SRC_DF] = None
    if _K_SRC_FP not in st.session_state: st.session_state[_K_SRC_FP] = ""
    if _K_RULES  not in st.session_state: st.session_state[_K_RULES]  = {}
    if _K_OUT_DF not in st.session_state: st.session_state[_K_OUT_DF] = None
    if _K_READY  not in st.session_state: st.session_state[_K_READY]  = False

def _file_fingerprint(upload) -> str:
    if upload is None:
        return ""
    name = getattr(upload, "name", "")
    try:
        size = len(upload.getvalue())
    except Exception:
        size = 0
    return f"{name}:{size}"

def render(session_slug: str = "dev_session") -> None:
    _init()
    app_header("Screen 3 — Roles • Collapse", "Assign rules by column, group, and collapse")

    # Entry log
    try:
        screen_log(session_slug, "s3", {"event": "enter", "ts": now_utc_iso()})
    except Exception:
        pass
    # Autoload + fingerprint guard
    try:
        meta = autoload_latest_artifacts(session_slug)
        chk = fingerprint_check(meta.get("upstream", {}), meta.get("current", {}))
        if not chk["ok"]:
            screen_log(session_slug, "s3", {"event": "fingerprint_mismatch", "reasons": chk["reasons"], "ts": now_utc_iso()})
            st.warning("Artifacts appear stale for this screen. Recompute or proceed with stale outputs (not recommended).")
            c1, c2 = st.columns(2)
            if c1.button("Recompute upstream"):
                st.session_state["force_recompute"] = True
                st.experimental_rerun()
            if not c2.button("Proceed with stale"):
                st.stop()
        else:
            screen_log(session_slug, "s3", {"event": "autoload", "ts": now_utc_iso()})
    except Exception:
        pass

    ver = int(st.session_state[_K_VER])

    # A) Source table — versioned uploader + change-sensitive parsing
    section_header("A) Source Table")
    up_src = st.file_uploader("Source table CSV (required)", type=["csv"], key=W_SRC(ver))

    curr_fp = _file_fingerprint(up_src)
    prev_fp = st.session_state[_K_SRC_FP]

    if up_src is None:
        pass
    elif curr_fp and curr_fp != prev_fp:
        try:
            st.session_state[_K_SRC_DF] = read_csv_lite(up_src)
            st.session_state[_K_OUT_DF] = None
            st.session_state[_K_READY]  = False
            st.session_state[_K_SRC_FP] = curr_fp
        except Exception as e:
            status_zone([{"level": "error", "text": f"Failed to read CSV: {e}"}])
            return

    df: pd.DataFrame | None = st.session_state[_K_SRC_DF]
    if df is None:
        status_zone([{"level": "info", "text": "Upload a source table to continue."}])
        return

    cols = list(df.columns)

    # B) Group-by keys
    section_header("B) Group-by Keys")
    selected_groups: List[str] = st.multiselect(
        "Select group-by columns",
        options=cols,
        key=W_GROUPS(ver),
    )

    # C) Rules per Column
    section_header("C) Rules per Column")
    rule_map: Dict[str, str] = dict(st.session_state[_K_RULES])
    for c in cols:
        if c in selected_groups:
            continue
        current = rule_map.get(c, "")
        rule = st.selectbox(
            f"{c}",
            options=[""] + _RULES,
            index=([""] + _RULES).index(current) if current in ([""] + _RULES) else 0,
            key=W_RULE(c, ver),
        )
        if rule:
            rule_map[c] = rule
        elif c in rule_map:
            rule_map.pop(c)
    st.session_state[_K_RULES] = rule_map

    # D) Execute
    section_header("D) Execute")
    messages: List[Dict[str, Any]] = []
    if st.button("Execute Collapse", key=f"s3_execute_v{ver}"):
        try:
            out_df, diag = run_collapse(df, selected_groups, rule_map)
            st.session_state[_K_OUT_DF] = out_df
            st.session_state[_K_READY]  = True
            # NEW: JSONL event
            screen_log(session_slug, "screen3", {
                "event": "execute",
                "group_keys": list(selected_groups),
                "rules": dict(rule_map),
                "rows_in": len(df),
                "rows_out": len(out_df),
                "ts": datetime.utcnow().isoformat() + "Z",
            })
            messages.append({"level": "success", "text": f"Collapse succeeded. Rows: {len(out_df)}"})
            messages.append({"level": "info", "text": f"Diagnostics: {json.dumps(diag)}"})
        except Exception as e:
            st.session_state[_K_OUT_DF] = None
            st.session_state[_K_READY]  = False
            messages.append({"level": "error", "text": f"Collapse error: {e}"})
    status_zone(messages)

    # E) Preview & Save
    section_header("E) Preview & Save")
    out_df: pd.DataFrame | None = st.session_state[_K_OUT_DF]
    if out_df is not None:
        table_preview(out_df, max_rows=100)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save Collapsed CSV", key=f"s3_save_csv_v{ver}"):
                try:
                    p = save_csv(out_df, f"{session_slug}_collapsed.csv", root=".")
                    st.success(f"Saved CSV → {p}")
                    st.code(str(p), language="text")
                    try:
                        from pathlib import Path as _P
                        screen_log(session_slug, "s3", {"event": "write", "artifact": _P(p).name, "path": str(p), "ts": now_utc_iso()})
                    except Exception:
                        pass
                    try:
                        from pathlib import Path as _P
                        screen_log(session_slug, "s3", {"event": "write", "artifact": _P(p).name, "path": str(p), "ts": now_utc_iso()})
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Save CSV failed: {e}")
        with c2:
            if st.button("Save Collapse Log", key=f"s3_save_log_v{ver}"):
                try:
                    log = {
                        "when": datetime.utcnow().isoformat() + "Z",
                        "group_keys": list(selected_groups),
                        "rules": dict(rule_map),
                        "rows_in": len(df),
                        "rows_out": len(out_df),
                    }
                    p = save_json(log, f"{session_slug}_collapse_log.json", root=".")
                    screen_log(session_slug, "screen3", {"event": "save_collapse_log", **log})  # NEW
                    st.success(f"Saved Log → {p}")
                    st.code(str(p), language="text")
                    try:
                        from pathlib import Path as _P
                        screen_log(session_slug, "s3", {"event": "write", "artifact": _P(p).name, "path": str(p), "ts": now_utc_iso()})
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Save Log failed: {e}")
    else:
        st.info("Execute to see preview.")

    # F) Navigation (canonical)
    st.divider()
    back_clicked, reset_clicked, next_clicked = nav_bar(
        back_enabled=True,
        next_enabled=bool(st.session_state[_K_READY]),
        on_next_label="Next \u2192",
    )

    if back_clicked:
        # In full app, router would navigate to Screen 2 here (no-op in slice)
        pass

    if reset_clicked:
        # Canonical: log and reset before creating widgets on next run
        screen_log(session_slug, "screen3", {"event": "nav_reset"})
        clear_keys([_K_SRC_DF, _K_OUT_DF, _K_SRC_FP])
        st.session_state[_K_RULES] = {}
        st.session_state[_K_READY] = False
        bump_version(_K_VER)
        st.rerun()

    if next_clicked:
        if st.session_state[_K_OUT_DF] is None:
            st.error("Nothing to pass on; Execute first.")
        else:
            screen_log(
                session_slug,
                "screen3",
                {"event": "nav_next", "rows_out": len(st.session_state[_K_OUT_DF]), "ts": datetime.utcnow().isoformat() + "Z"},
            )  # NEW
            st.success("Ready for next screen (Modeling).")
