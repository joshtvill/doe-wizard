# app.py
import streamlit as st
from ui.blocks import page_header, status
from screens.session_setup import render as render_session_setup
from screens.files_join_profile import render as render_files_join_profile
from screens.roles_collapse import render as render_roles_collapse  # NEW

st.set_page_config(page_title="CMP AI-Guided DOE Workflow (Phase-1)", layout="wide")

def main():
    page_header("CMP AI-Guided DOE Workflow (Phase-1)")
    st.caption("Phase-1: Session Setup → Files/Join/Profile → Roles/Collapse")

    st.sidebar.header("Navigation")
    screen = st.sidebar.radio(
        label="Go to:",
        options=[
            "Screen 1 — Session Setup",
            "Screen 2 — Files / Join / Profile",
            "Screen 3 — Roles & Collapse",  # NEW
        ],
        index=0,
        label_visibility="collapsed",
    )

    if screen.startswith("Screen 1"):
        render_session_setup()
    elif screen.startswith("Screen 2"):
        render_files_join_profile()
    elif screen.startswith("Screen 3"):
        render_roles_collapse()  # NEW
    else:
        status("Screen not implemented yet.", "warn")

if __name__ == "__main__":
    main()
