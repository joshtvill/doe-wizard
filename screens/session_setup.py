# screens/session_setup.py
"""
Screen 1 — Session Setup (thin)
Creates the session slug, objective, response metric label, optional metadata, and writes
artifacts/<slug>_session_setup.json. Also appends JSONL screen events via utils.screenlog.

NOTE: This screen exposes a callable `render()` for the router, matching other screens.
"""

from __future__ import annotations
from typing import Optional, List
import streamlit as st

from services.session_setup_store import default_slug, build_payload, write_payload
from utils.screenlog import screen_log  # shared JSONL writer
from utils.runtime import now_utc_iso
from ui.blocks import nav_bar           # canonical nav (Back / Reset / Next)

# --- Session-state keys (local to Screen 1) ---
_K_VER    = "s1_ver"             # version to force re-instantiation of widgets
_K_RESET  = "s1_reset_pending"   # flag to clear inputs on next run

# We keep these names purely for clarity; widgets will carry version suffixes.
_K_SLUG   = "s1_slug"
_K_OBJ    = "s1_objective"
_K_METRIC = "s1_response_metric"
_K_OWNER  = "s1_owner"
_K_TAGS   = "s1_tags"
_K_CTX    = "s1_context"


def _ensure_version_keys() -> int:
    """Initialize version + reset flag if missing; return current version."""
    if _K_VER not in st.session_state:
        st.session_state[_K_VER] = 0
    if _K_RESET not in st.session_state:
        st.session_state[_K_RESET] = False
    return int(st.session_state[_K_VER])


def _apply_reset_if_pending() -> None:
    """
    If the previous click requested a reset, clear S1 inputs BEFORE creating widgets,
    then unset the flag so the render proceeds with fresh defaults.
    """
    if st.session_state.get(_K_RESET, False):
        # Clear any cached values so fields show fresh defaults on this run.
        for k in (_K_SLUG, _K_OBJ, _K_METRIC, _K_OWNER, _K_TAGS, _K_CTX):
            if k in st.session_state:
                del st.session_state[k]
        # Also drop any cached cross-screen slug so default_slug() can regenerate.
        if "session_slug" in st.session_state:
            del st.session_state["session_slug"]
        # Reset complete for this run
        st.session_state[_K_RESET] = False


def render(session_slug: Optional[str] = None) -> None:
    st.title("Screen 1 — Session Setup")

    # Entry log (JSONL)
    try:
        slug_for_log = (st.session_state.get("session_slug") if "session_slug" in st.session_state else None) or (session_slug or default_slug("run"))
        screen_log(slug_for_log, "s1", {"event": "enter", "ts": now_utc_iso()})
    except Exception:
        pass

    # Prepare versioning + honor any pending reset BEFORE creating widgets
    ver = _ensure_version_keys()
    _apply_reset_if_pending()

    # 1) Inputs (minimal, HITL-friendly)
    st.subheader("1) Identify the session")
    initial_slug = st.session_state.get("session_slug") if "session_slug" in st.session_state else None
    slug = st.text_input(
        "Session slug",
        key=f"{_K_SLUG}_{ver}",
        value=st.session_state.get(_K_SLUG, initial_slug or default_slug("run")),
        help="A short, unique ID for this DOE session.",
    )

    st.subheader("2) Objective & metric")
    objective = st.text_area(
        "Process objective (plain English)",
        key=f"{_K_OBJ}_{ver}",
        value=st.session_state.get(_K_OBJ, ""),
        placeholder="e.g., Minimize within-wafer non-uniformity while holding removal rate ≥ 250 nm/min.",
    )
    response_metric = st.text_input(
        "Response Metric label",
        key=f"{_K_METRIC}_{ver}",
        value=st.session_state.get(_K_METRIC, "response_metric"),
        help="This is how the response column will be referred to downstream.",
    )

    st.subheader("3) Optional metadata")
    owner = st.text_input("Owner (optional)", key=f"{_K_OWNER}_{ver}", value=st.session_state.get(_K_OWNER, ""))
    tags_str = st.text_input("Tags (comma-separated, optional)", key=f"{_K_TAGS}_{ver}", value=st.session_state.get(_K_TAGS, ""))
    context = st.text_area("Context/notes (optional)", height=100, key=f"{_K_CTX}_{ver}", value=st.session_state.get(_K_CTX, ""))

    # 2) Actions
    col1, col2 = st.columns(2)
    with col1:
        clicked_write = st.button("Save Session Setup", type="primary", key="s1_btn_save")
    with col2:
        clicked_enter = st.button("Enter (log screen_enter)", key="s1_btn_enter")

    # 3) Behavior
    if clicked_enter:
        screen_log(slug, "screen1", {"event": "screen_enter"})
        st.success("Entered Screen 1 (event logged).")

    def _save_now() -> str:
        """Save current inputs to <slug>_session_setup.json and log JSONL; return path."""
        tags: Optional[List[str]] = None
        if (tags_str or "").strip():
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        payload = build_payload(
            slug=(slug or "").strip() or default_slug("run"),
            objective=(objective or "").strip() or "N/A",
            response_metric=(response_metric or "").strip() or "response_metric",
            context=(context or "").strip() or None,
            owner=(owner or "").strip() or None,
            tags=tags or None,
        )
        path = write_payload(payload)
        screen_log(slug, "screen1", {"event": "save_setup", "path": path, "slug": payload["slug"]})
        # Write event (canonical)
        try:
            from pathlib import Path as _P
            screen_log(payload["slug"], "s1", {"event": "write", "artifact": _P(path).name, "path": str(path), "ts": now_utc_iso()})
        except Exception:
            pass

        # Make slug available to S2+
        st.session_state["session_slug"] = payload["slug"]
        st.success(f"Session saved → {path}")
        st.caption("You can proceed to Screen 2 (Files · Join · Profile).")
        return path

    if clicked_write:
        _save_now()

    # --- Canonical nav bar (Back / Reset / Next) ---
    st.divider()
    back_clicked, reset_clicked, next_clicked = nav_bar(
        back_enabled=False,                       # first screen
        next_enabled=bool((slug or "").strip()), # gate Next on non-empty slug
        on_next_label="Next →",
    )

    if back_clicked:
        pass  # no-op on first screen

    if reset_clicked:
        # Mark reset for next run, bump version so keys change, then rerun
        screen_log(slug, "screen1", {"event": "nav_reset"})
        st.session_state[_K_RESET] = True
        st.session_state[_K_VER] = int(st.session_state.get(_K_VER, 0)) + 1
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    if next_clicked:
        path = _save_now()
        screen_log(slug, "screen1", {"event": "nav_next", "path": path})
        # Router would advance to Screen 2 here
