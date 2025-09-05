# app.py
"""
DOE Wizard — central router with env-gated dev sidebar.

Phase 1 goals:
- Screens are thin orchestrators that call adapters only and return a dict.
- Routing and navigation live here (no sidebar nav in prod).
- Dev-only sidebar (screen jump) is enabled only when DOE_WIZARD_DEBUG=1.
- No disk writes occur in screens; this file performs no I/O either.
"""

import os
import streamlit as st

# Screen render imports (each returns {"valid_to_proceed": bool, "payload": dict})
from screens.session_setup import render as render_s1
from screens.files_join_profile import render as render_s2
from screens.roles_collapse import render as render_s3
from screens.modeling import render as render_s4
from screens.optimization import render as render_s5
from screens.handoff import render as render_s6

# Shared UI blocks
from ui.blocks import nav_back_reset_next


# Ordered list of screens (title, render_fn)
SCREENS = [
    ("S1 — Session Setup", render_s1),
    ("S2 — Files · Join · Profile", render_s2),
    ("S3 — Roles & Collapse", render_s3),
    ("S4 — Modeling", render_s4),
    ("S5 — Optimization", render_s5),
    ("S6 — Handoff", render_s6),
]


def main() -> None:
    st.set_page_config(page_title="DOE Wizard", layout="wide")

    # Initialize router position
    if "screen_idx" not in st.session_state:
        st.session_state.screen_idx = 0

    # ---- Dev-only sidebar (env-gated) ----
    # Toggle with: $env:DOE_WIZARD_DEBUG="1"  (PowerShell)
    debug = os.getenv("DOE_WIZARD_DEBUG", "0") == "1"
    if debug:
        with st.sidebar:
            st.subheader("Dev Tools")
            st.caption("Debug sidebar active (set DOE_WIZARD_DEBUG=1 to show)")
            st.radio(
                "Jump to screen",
                options=[f"{i}: {title}" for i, (title, _) in enumerate(SCREENS)],
                index=st.session_state.screen_idx,
                key="dev_jump_choice",
            )
            # Parse selected index from "i: Title"
            try:
                chosen_prefix = str(st.session_state.dev_jump_choice).split(":")[0].strip()
                new_idx = int(chosen_prefix)
                if new_idx != st.session_state.screen_idx:
                    st.session_state.screen_idx = new_idx
                    st.rerun()
            except Exception:
                pass  # keep current index if parsing fails

    # ---- Render current screen ----
    title, renderer = SCREENS[st.session_state.screen_idx]
    st.markdown(f"### {title}")

    result = renderer() or {}
    valid = bool(result.get("valid_to_proceed", False))

    # ---- Footer navigation (Back / Next) ----
    back_clicked, reset_clicked, next_clicked = nav_back_reset_next(valid_to_proceed=valid)

    if back_clicked and st.session_state.screen_idx > 0:
        st.session_state.screen_idx -= 1
        st.rerun()

    if reset_clicked:
        # Clear all UI/session selections and return to S1
        st.session_state.clear()
        st.session_state.screen_idx = 0
        st.rerun()

    if next_clicked and valid and st.session_state.screen_idx < len(SCREENS) - 1:
        st.session_state.screen_idx += 1
        st.rerun()


if __name__ == "__main__":
    main()
