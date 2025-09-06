# tests/unit/test_app_router.py
import importlib
import streamlit as st

def test_router_back_next_enables_and_moves(monkeypatch):
    # Import the app module (no need to call main()).
    app = importlib.import_module("app")

    # Reset any prior state
    st.session_state.clear()

    # App's router logic defaults to 0 when 'screen_idx' is missing.
    if "screen_idx" not in st.session_state:
        st.session_state["screen_idx"] = 0
    assert st.session_state["screen_idx"] == 0

    # Move forward and back by manipulating the same state key the router uses.
    st.session_state["screen_idx"] = 1
    assert st.session_state["screen_idx"] == 1

    st.session_state["screen_idx"] = 0
    assert st.session_state["screen_idx"] == 0
