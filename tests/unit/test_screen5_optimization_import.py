# Ensures the screen module can be imported without raising,
# even when required session state is minimal (no autorun).
import streamlit as st

def test_screen5_import_no_autorun():
    st.session_state.clear()
    st.session_state["session_slug"] = "testslug"
    # no autorun here; just import and ensure no exceptions
    import importlib
    mod = importlib.import_module("screens.optimization")
    assert hasattr(mod, "st")  # module loaded
