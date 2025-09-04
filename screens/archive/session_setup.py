"""
screens/session_setup.py

Screen 1 — Session Setup (thin screen)
--------------------------------------
Responsibility:
- UI to capture context, objective, response (no heavy logic)
- Delegate persistence to services.session_setup_store (contract v3 naming)
- Manage state via flag → rerun → apply pattern (no mutate-after-widget)
- Surface existing sessions (discover) and allow loading (prefill)

Artifact naming (contract v3, locked):
    artifacts/<session_slug>-session-setup.json
Where:
    session_slug = YYMMDD-<context>-<objective>-<response> (dashes only)

Public entrypoint:
    render()

Expected global state keys (non-breaking if absent):
    session_context: str
    session_objective: str
    session_response: str
    current_session_slug: str
"""

from __future__ import annotations

import streamlit as st

# Optional shared UI helpers; screen still works if these imports fail.
try:
    from ui.blocks import page_header  # type: ignore
except Exception:  # pragma: no cover
    page_header = None  # fallback: render simple header

# Persistence (functionality-scoped store)
from services.session_setup_store import (
    save_new_session_setup,
    discover_session_setups,
    load_session_setup,
)

# -----------------------
# Internal constants/keys
# -----------------------
_SCREEN_TITLE = "Screen 1 — Session Setup"
_KEY_CTX = "session_context"
_KEY_OBJ = "session_objective"
_KEY_RESP = "session_response"
_KEY_CURR_SLUG = "current_session_slug"

_FLAG_PENDING_LOAD = "_pending_load_slug"       # slug to load pre-widgets
_FLAG_PENDING_RESET = "_pending_reset_screen1"  # reset Screen 1 fields pre-widgets
_FLAG_LAST_SAVE_MSG = "_last_save_message"      # transient info banner


def _init_defaults() -> None:
    """Ensure default keys exist without overwriting user input."""
    ss = st.session_state
    ss.setdefault(_KEY_CTX, "")
    ss.setdefault(_KEY_OBJ, "maximize")
    ss.setdefault(_KEY_RESP, "")
    # _KEY_CURR_SLUG is optional; set only when Save/Load succeeds


def _apply_pending_reset_if_any() -> None:
    """
    Apply a pending reset BEFORE widgets are created.
    Clears Screen 1 fields, preserves current_session_slug, clears flag, then reruns.
    """
    ss = st.session_state
    if not ss.get(_FLAG_PENDING_RESET):
        return
    # reset fields safely (pre-widgets)
    ss[_KEY_CTX] = ""
    ss[_KEY_OBJ] = "maximize"
    ss[_KEY_RESP] = ""
    ss.pop(_FLAG_PENDING_RESET, None)
    st.rerun()


def _apply_pending_load_if_any() -> None:
    """
    Apply a pending load BEFORE widgets are created.
    Uses flag → load payload → set fields → clear flag → rerun.
    """
    ss = st.session_state
    pending = ss.get(_FLAG_PENDING_LOAD)
    if not pending:
        return

    try:
        payload = load_session_setup(pending)
        ss[_KEY_CTX] = payload.get("context", "")
        ss[_KEY_OBJ] = payload.get("objective", "maximize")
        ss[_KEY_RESP] = payload.get("response", "")
        ss[_KEY_CURR_SLUG] = payload.get("session_slug", pending)
        ss.pop(_FLAG_PENDING_LOAD, None)
        st.rerun()
    except FileNotFoundError:
        ss.pop(_FLAG_PENDING_LOAD, None)
        ss[_FLAG_LAST_SAVE_MSG] = f"Could not find session for slug: {pending}"
        st.rerun()
    except Exception as e:
        ss.pop(_FLAG_PENDING_LOAD, None)
        ss[_FLAG_LAST_SAVE_MSG] = f"Failed to load session ({pending}): {e}"
        st.rerun()


def render() -> None:
    """Render Screen 1 (no set_page_config here; app.py owns it)."""
    _init_defaults()
    # Handle resets and loads BEFORE creating any widgets
    _apply_pending_reset_if_any()
    _apply_pending_load_if_any()

    ss = st.session_state

    # Header
    if page_header:
        page_header(_SCREEN_TITLE)
    else:
        st.markdown(f"## {_SCREEN_TITLE}")

    # Info banner (last action)
    last_msg = ss.pop(_FLAG_LAST_SAVE_MSG, None)
    if last_msg:
        st.info(last_msg)

    # Layout: inputs (left) | existing sessions (right)
    col_left, col_right = st.columns([2, 1], gap="large")

    with col_left:
        st.markdown("#### Define or edit session")
        st.text_input("Context tag", key=_KEY_CTX, placeholder="e.g., cmp-pilot")
        st.selectbox("Objective", options=["maximize", "minimize"], key=_KEY_OBJ)
        st.text_input("Response metric", key=_KEY_RESP, placeholder="e.g., mrr")

        # Current active slug (if any)
        if ss.get(_KEY_CURR_SLUG):
            st.caption(f"Active session slug: **{ss[_KEY_CURR_SLUG]}**")

        # Actions
        save_col, load_col, reset_col = st.columns(3)
        with save_col:
            if st.button("Save new session", use_container_width=True):
                _on_click_save()
        with load_col:
            if st.button("Load selected", use_container_width=True):
                selected_slug = ss.get("_session_picker_slug", "")
                if selected_slug:
                    ss[_FLAG_PENDING_LOAD] = selected_slug
                    st.rerun()
                else:
                    ss[_FLAG_LAST_SAVE_MSG] = "No session selected to load."
                    st.rerun()
        with reset_col:
            if st.button("Reset fields", use_container_width=True):
                # set reset flag and rerun; actual mutation happens pre-widgets
                ss[_FLAG_PENDING_RESET] = True
                st.rerun()

    with col_right:
        st.markdown("#### Existing sessions")
        sessions = discover_session_setups(limit=None)
        if not sessions:
            st.write("No saved sessions yet.")
        else:
            # Build label list: "YYMMDD-context-objective-response  (mtime)"
            labels = [
                f"{slug}  ({mtime_iso_utc})"
                for (slug, _path, mtime_iso_utc) in sessions
            ]
            # Default selection to current session if present
            default_index = 0
            current_slug = ss.get(_KEY_CURR_SLUG, "")
            if current_slug:
                for i, (slug, _, _) in enumerate(sessions):
                    if slug == current_slug:
                        default_index = i
                        break

            sel = st.selectbox(
                "Pick a session to load",
                options=list(range(len(labels))),
                format_func=lambda i: labels[i],
                index=default_index if sessions else 0,
                key="_session_picker_index",
            )
            # Cache the selected slug for the Load button
            if 0 <= sel < len(sessions):
                picked_slug = sessions[sel][0]
                ss["_session_picker_slug"] = picked_slug
                st.caption(f"Selected slug: **{picked_slug}**")

    # Footer note
    st.markdown(
        "<span style='font-size:0.9em;color:gray;'>"
        "Tip: Saving creates a new JSON under <code>artifacts/</code> using contract v3 naming "
        "(<code>&lt;session_slug&gt;-session-setup.json</code>). Loading will prefill fields. "
        "Reset uses a safe flag → rerun → apply pattern."
        "</span>",
        unsafe_allow_html=True,
    )


# ---------------
# Button handlers
# ---------------

def _on_click_save() -> None:
    """Handle Save new session (validates then delegates to the store)."""
    ss = st.session_state
    context = (ss.get(_KEY_CTX) or "").strip()
    objective = (ss.get(_KEY_OBJ) or "").strip()
    response = (ss.get(_KEY_RESP) or "").strip()

    # Simple validations
    errors = []
    if not context:
        errors.append("Context is required.")
    if objective not in {"maximize", "minimize"}:
        errors.append("Objective must be 'maximize' or 'minimize'.")
    if not response:
        errors.append("Response metric is required.")

    if errors:
        st.error(" ".join(errors))
        return

    try:
        slug, path = save_new_session_setup(context, objective, response)
        ss[_KEY_CURR_SLUG] = slug
        ss[_FLAG_LAST_SAVE_MSG] = f"Saved session: {slug} → {path}"
        st.rerun()
    except Exception as e:
        st.error(f"Failed to save session: {e}")
