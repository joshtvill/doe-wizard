"""
tests/unit/test_utils_app_init.py
Ensures init helpers set non-widget defaults and preserve existing session_slug.
"""

from pathlib import Path
import streamlit as st

from utils.app_init import ensure_artifacts_dir, init_session_state

def test_ensure_artifacts_dir(tmp_path: Path):
    target = tmp_path / "artifacts"
    assert not target.exists()
    ensure_artifacts_dir(target)
    assert target.exists() and target.is_dir()

def test_init_session_state_sets_defaults(tmp_path: Path):
    # Reset session_state for this test scope
    st.session_state.clear()
    init_session_state(app_version="0.1.0", artifacts_dir=tmp_path)
    assert st.session_state["app_version"] == "0.1.0"
    assert st.session_state["artifacts_dir"] == str(tmp_path)
    assert st.session_state["current_page"] == "Session Setup"
    assert st.session_state["last_page"] == "Session Setup"
    assert "session_slug" in st.session_state  # default None ok

def test_init_session_state_preserves_slug(tmp_path: Path):
    st.session_state.clear()
    st.session_state["session_slug"] = "pre_set_slug_123"
    init_session_state(app_version="0.1.0", artifacts_dir=tmp_path)
    assert st.session_state["session_slug"] == "pre_set_slug_123"
