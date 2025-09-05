# screens/files_join_profile.py
"""
Screen 2 — Files • Join • Profiling (MVP, debounced)
Uploads, optional join, profiling, previews, saves, autosave on Next, and HITL warning ack.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Any, Optional
import json, hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

from ui.blocks import (
    app_header, section_header, status_zone,
    table_summary_preview, columns_profile_preview, table_preview, nav_bar,
)
from services.file_io import read_csv_lite
from services.joiner import left_join, JoinerError
from services.profiler import profile_table
from services.artifacts import save_json, save_csv
from utils.constants import PROF_SAMPLE_CAP
from utils.screenlog import screen_log  # NEW
from utils.time import now_utc_iso
from state import autoload_latest_artifacts, fingerprint_check

# --- Session-state keys (local to Screen 2) ---
_K_FEATURES = "s2_features_df"
_K_RESPONSE = "s2_response_df"
_K_KEYS     = "s2_join_key_pairs"       # List[Tuple[str,str]]
_K_MERGED   = "s2_merged_df"
_K_PROFILE  = "s2_profile_payload"      # {'table_summary':..., 'columns_profile':[...]}
_K_DIAG     = "s2_join_diagnostics"
_K_ACK      = "s2_ack_join_warnings"
_K_FPRINT   = "s2_last_execute_fingerprint"
_K_READY    = "s2_ready_for_next"
_K_WARN     = "s2_warning_active"
_K_UPVER    = "s2_uploader_version"     # increments to clear upload widgets

_PREVIEW_ROWS = 100

def _init_state() -> None:
    defaults = {
        _K_FEATURES: None, _K_RESPONSE: None,
        _K_KEYS: [], _K_MERGED: None, _K_PROFILE: None,
        _K_DIAG: None, _K_ACK: False, _K_FPRINT: "",
        _K_READY: False, _K_WARN: False, _K_UPVER: 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _file_meta(upload) -> tuple[str, int]:
    if upload is None:
        return ("", 0)
    try:
        return (getattr(upload, "name", "") or "", len(upload.getvalue()))
    except Exception:
        return (getattr(upload, "name", "") or "", 0)

def _fingerprint(features_file, response_file, key_pairs: List[Tuple[str, str]]) -> str:
    lf, ls = _file_meta(features_file)
    rf, rs = _file_meta(response_file)
    payload = json.dumps({"lf": lf, "ls": ls, "rf": rf, "rs": rs, "keys": key_pairs}, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()

def _reset_screen2_state() -> None:
    # Clear dataframes, diagnostics, profile, readiness/ack
    for k in (_K_FEATURES, _K_RESPONSE, _K_MERGED, _K_PROFILE, _K_DIAG):
        st.session_state[k] = None
    for k in (_K_ACK, _K_READY, _K_WARN):
        st.session_state[k] = False
    st.session_state[_K_KEYS] = []
    st.session_state[_K_FPRINT] = ""
    # Force-clear file_uploader widgets by bumping version
    st.session_state[_K_UPVER] = int(st.session_state.get(_K_UPVER, 0)) + 1

def _join_warning_active(diag: Optional[Dict[str, Any]]) -> bool:
    if not diag:
        return False
    return (
        (diag.get("join_rate", 1.0) < 0.95) or
        (diag.get("left_only", 0) > 0) or
        (diag.get("right_only", 0) > 0) or
        (diag.get("dup_key_left", 0) > 0) or
        (diag.get("dup_key_right", 0) > 0)
    )

def _save_profile_json(session_slug: str, profile_payload: Dict[str, Any]) -> str:
    p = save_json(profile_payload, f"{session_slug}_profile.json", root=".")
    try:
        from pathlib import Path as _P
        screen_log(session_slug, "s2", {"event": "write", "artifact": _P(p).name, "path": str(p), "ts": now_utc_iso()})
    except Exception:
        pass
    return str(p)

def _save_merged_and_profile(session_slug: str, merged_df: pd.DataFrame, profile_payload: Dict[str, Any]) -> tuple[str, str]:
    p_csv = save_csv(merged_df, f"{session_slug}_merged.csv", root=".")
    p_json = save_json(profile_payload, f"{session_slug}_profile.json", root=".")
    try:
        from pathlib import Path as _P
        screen_log(session_slug, "s2", {"event": "write", "artifact": _P(p_csv).name, "path": str(p_csv), "ts": now_utc_iso()})
        screen_log(session_slug, "s2", {"event": "write", "artifact": _P(p_json).name, "path": str(p_json), "ts": now_utc_iso()})
    except Exception:
        pass
    return str(p_csv), str(p_json)

# --- callbacks to avoid double-fire / mid-render mutation ---
def _cb_add_key():
    st.session_state[_K_KEYS] = st.session_state.get(_K_KEYS, []) + [("", "")]

def _cb_remove_key():
    keys = st.session_state.get(_K_KEYS, [])
    if len(keys) > 1:
        st.session_state[_K_KEYS] = keys[:-1]

def render(session_slug: str = "dev_session") -> None:
    _init_state()
    # Entry log
    try:
        screen_log(session_slug, "s2", {"event": "enter", "ts": now_utc_iso()})
    except Exception:
        pass
    # Autoload + fingerprint guard
    try:
        meta = autoload_latest_artifacts(session_slug)
        chk = fingerprint_check(meta.get("upstream", {}), meta.get("current", {}))
        if not chk["ok"]:
            screen_log(session_slug, "s2", {"event": "fingerprint_mismatch", "reasons": chk["reasons"], "ts": now_utc_iso()})
            st.warning("Artifacts appear stale for this screen. Recompute or proceed with stale outputs (not recommended).")
            c1, c2 = st.columns(2)
            if c1.button("Recompute upstream"):
                st.session_state["force_recompute"] = True
                st.experimental_rerun()
            if not c2.button("Proceed with stale"):
                st.stop()
        else:
            screen_log(session_slug, "s2", {"event": "autoload", "ts": now_utc_iso()})
    except Exception:
        pass
    app_header("Screen 2 — Files • Join • Profiling", "Upload, optional join, profile, preview, and save")

    # A) Uploads (use versioned keys so Reset clears widget selections)
    section_header("A) Uploads")
    ver = int(st.session_state[_K_UPVER])
    up_features = st.file_uploader("Features CSV (required)", type=["csv"], key=f"s2_up_features_{ver}")
    up_response = st.file_uploader("Response CSV (optional)", type=["csv"], key=f"s2_up_response_{ver}")

    if up_features is not None:
        try:
            st.session_state[_K_FEATURES] = read_csv_lite(up_features)
        except Exception as e:
            status_zone([{"level": "error", "text": f"Failed to read Features CSV: {e}"}])
            st.stop()

    if up_response is not None:
        try:
            st.session_state[_K_RESPONSE] = read_csv_lite(up_response)
        except Exception as e:
            status_zone([{"level": "error", "text": f"Failed to read Response CSV: {e}"}])
            st.stop()

    # Any input change invalidates readiness until Execute
    current_fp = _fingerprint(up_features, up_response, st.session_state[_K_KEYS])
    if st.session_state[_K_FPRINT] != current_fp:
        st.session_state[_K_READY] = False
        st.session_state[_K_ACK] = False

    # B) Join key selection (visible only if Response uploaded)
    keys_shown = st.session_state[_K_RESPONSE] is not None
    if keys_shown and len(st.session_state[_K_KEYS]) == 0:
        st.session_state[_K_KEYS] = [("", "")]

    if keys_shown:
        section_header("B) Join key selection")
        left_cols = list(st.session_state[_K_FEATURES].columns) if st.session_state[_K_FEATURES] is not None else []
        right_cols = list(st.session_state[_K_RESPONSE].columns) if st.session_state[_K_RESPONSE] is not None else []

        # Build a new list to avoid mid-render mutations causing extra rows
        new_keys: List[Tuple[str, str]] = []
        for i, (lval, rval) in enumerate(st.session_state[_K_KEYS]):
            c1, c2 = st.columns(2)
            with c1:
                l_opts = [""] + left_cols
                lval = st.selectbox(
                    f"Left key #{i+1}",
                    l_opts,
                    index=l_opts.index(lval) if lval in l_opts else 0,
                    key=f"s2_left_{i}_{ver}",
                )
            with c2:
                r_opts = [""] + right_cols
                rval = st.selectbox(
                    f"Right key #{i+1}",
                    r_opts,
                    index=r_opts.index(rval) if rval in r_opts else 0,
                    key=f"s2_right_{i}_{ver}",
                )
            new_keys.append((lval, rval))
        st.session_state[_K_KEYS] = new_keys

        cadd, crem = st.columns(2)
        with cadd:
            st.button("Add key pair", on_click=_cb_add_key, key=f"btn_add_keypair_{ver}")
        with crem:
            st.button("Remove key pair", on_click=_cb_remove_key, disabled=len(st.session_state[_K_KEYS]) <= 1, key=f"btn_remove_keypair_{ver}")

    # C) Execute
    section_header("C) Execute")
    clicked_execute = st.button("Execute (join + profile)" if keys_shown else "Execute (profile features)", key=f"btn_execute_{ver}")

    messages: List[Dict[str, Any]] = []
    if clicked_execute:
        if st.session_state[_K_FEATURES] is None:
            messages.append({"level": "error", "text": "Features CSV is required."})
        else:
            try:
                active_df = st.session_state[_K_FEATURES]
                st.session_state[_K_DIAG] = None
                st.session_state[_K_MERGED] = None

                if keys_shown:
                    # Enforce: ignore rows with both sides blank; error if partially filled; require ≥1 complete
                    filtered_keys: List[Tuple[str, str]] = []
                    partial_found = False
                    for (l, r) in st.session_state[_K_KEYS]:
                        if l and r:
                            filtered_keys.append((l, r))
                        elif (l and not r) or (r and not l):
                            partial_found = True
                    if partial_found:
                        raise JoinerError("Each key pair row must have BOTH left and right selected, or leave BOTH blank.")
                    if len(filtered_keys) == 0:
                        raise JoinerError("Define at least one complete (left,right) key pair or remove the Response CSV.")

                    merged_df, join_diag = left_join(st.session_state[_K_FEATURES], st.session_state[_K_RESPONSE], filtered_keys)
                    st.session_state[_K_MERGED] = merged_df
                    st.session_state[_K_DIAG] = join_diag
                    active_df = merged_df

                # Profile
                st.session_state[_K_PROFILE] = profile_table(active_df, sample_cap=PROF_SAMPLE_CAP)

                # Warning + readiness
                warn_active = _join_warning_active(st.session_state[_K_DIAG])
                st.session_state[_K_WARN] = warn_active
                if not warn_active:
                    st.session_state[_K_ACK] = False

                st.session_state[_K_FPRINT] = current_fp
                st.session_state[_K_READY] = (st.session_state[_K_PROFILE] is not None) and (not warn_active or st.session_state[_K_ACK])

                # NEW: JSONL event
                screen_log(session_slug, "screen2", {
                    "event": "execute",
                    "joined": bool(st.session_state[_K_MERGED] is not None),
                    "join_diag": st.session_state[_K_DIAG] or {},
                    "profile_cols": len(st.session_state[_K_PROFILE].get("columns_profile", [])) if st.session_state[_K_PROFILE] else 0,
                    "fingerprint": current_fp,
                    "ts": datetime.utcnow().isoformat() + "Z",
                })

                messages.append({"level": "success", "text": "Execute succeeded."})
            except JoinerError as je:
                messages.append({"level": "error", "text": f"Join error: {je}"})
            except Exception as e:
                messages.append({"level": "error", "text": f"Unexpected error during Execute: {e}"})

    # Status + ack (ack immediately lifts gate without re-execute)
    if st.session_state[_K_WARN]:
        messages.append({"level": "warning", "text": "Join quality concerns detected. Review diagnostics and acknowledge to proceed."})
        prev_ack = st.session_state[_K_ACK]
        st.session_state[_K_ACK] = st.checkbox(
            "I understand the join warnings and want to proceed.",
            value=st.session_state[_K_ACK],
            key=f"chk_ack_join_warn_{ver}",
        )
        if st.session_state[_K_ACK] != prev_ack:
            st.session_state[_K_READY] = (st.session_state[_K_PROFILE] is not None) and st.session_state[_K_ACK]
            if st.session_state[_K_ACK]:
                try:
                    screen_log(session_slug, "s2", {"event": "gate_ack", "type": "join_warn_ack", "ts": now_utc_iso()})
                except Exception:
                    pass

    status_zone(messages)

    # D) Previews
    section_header("D) Previews")
    profile_payload = st.session_state[_K_PROFILE] or {}
    table_summary_preview(profile_payload.get("table_summary", {}))
    columns_profile_preview(profile_payload.get("columns_profile", []))
    active_df = st.session_state[_K_MERGED] if st.session_state[_K_MERGED] is not None else st.session_state[_K_FEATURES]
    if active_df is not None:
        table_preview(active_df, max_rows=_PREVIEW_ROWS)

    # E) Save
    section_header("E) Save")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("JSON only — Save Profile", key=f"btn_save_profile_json_{ver}"):
            if st.session_state[_K_PROFILE] is None:
                st.error("Nothing to save yet. Execute first.")
            else:
                p = _save_profile_json(session_slug, st.session_state[_K_PROFILE])
                st.success(f"Saved profile JSON → {p}")
    with col2:
        if st.button("Save Merged CSV + Profile JSON", disabled=(st.session_state[_K_MERGED] is None), key=f"btn_save_both_{ver}"):
            if st.session_state[_K_MERGED] is None or st.session_state[_K_PROFILE] is None:
                st.error("Nothing to save yet. Execute first with Response present.")
            else:
                p_csv, p_json = _save_merged_and_profile(session_slug, st.session_state[_K_MERGED], st.session_state[_K_PROFILE])
                st.success(f"Saved merged CSV → {p_csv}\nSaved profile JSON → {p_json}")

    # F) Navigation (canonical)
    st.divider()
    back_clicked, reset_clicked, next_clicked = nav_bar(
        back_enabled=True,
        next_enabled=bool(st.session_state[_K_READY]),
        on_next_label="Next \u2192",
    )

    if back_clicked:
        # In full app, router would navigate to Screen 1 here (no-op in slice)
        pass

    if reset_clicked:
        # Canonical: log and reset before creating widgets on next run
        screen_log(session_slug, "screen2", {"event": "nav_reset"})
        _reset_screen2_state()
        st.rerun()  # Clear uploads + previews by bumping uploader version

    if next_clicked:
        if st.session_state[_K_PROFILE] is None:
            st.error("Profile missing; cannot proceed.")
        else:
            save_json(st.session_state[_K_PROFILE], f"{session_slug}_profile.json", root=".")
            run_log = {
                "when": datetime.utcnow().isoformat() + "Z",
                "fingerprint": st.session_state[_K_FPRINT],
                "joined": st.session_state[_K_MERGED] is not None,
                "join_diagnostics": st.session_state[_K_DIAG] or {},
                "profile_rows": len(st.session_state[_K_PROFILE].get("columns_profile", [])),
            }
            # Keep existing JSON (back-compat) and ALSO write JSONL
            save_json(run_log, f"{session_slug}_screen2_log.json", root=".")
            screen_log(session_slug, "screen2", {"event": "nav_next", **run_log})
            st.success("Autosaved profile + log. (Routing to Screen 3 would happen here.)")
