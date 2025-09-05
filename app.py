import streamlit as st
from ui.blocks import nav_back_next

from screens.session_setup import render as render_s1
from screens.files_join_profile import render as render_s2
from screens.roles_collapse import render as render_s3
from screens.modeling import render as render_s4
from screens.optimization import render as render_s5
from screens.handoff import render as render_s6

SCREENS = [
    ("S1 — Session Setup", render_s1),
    ("S2 — Files · Join · Profile", render_s2),
    ("S3 — Roles & Collapse", render_s3),
    ("S4 — Modeling", render_s4),
    ("S5 — Optimization", render_s5),
    ("S6 — Handoff", render_s6),
]

def main():
    st.set_page_config(page_title="DOE Wizard", layout="wide")

    if "screen_idx" not in st.session_state:
        st.session_state.screen_idx = 0

    title, renderer = SCREENS[st.session_state.screen_idx]
    st.markdown(f"### {title}")

    result = renderer() or {}
    valid = bool(result.get("valid_to_proceed", False))

    prev_clicked, next_clicked = nav_back_next(valid_to_proceed=valid)

    if prev_clicked and st.session_state.screen_idx > 0:
        st.session_state.screen_idx -= 1
        st.rerun()
    if next_clicked and valid and st.session_state.screen_idx < len(SCREENS) - 1:
        st.session_state.screen_idx += 1
        st.rerun()

if __name__ == "__main__":
    main()
