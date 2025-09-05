# tests/unit/test_app_router.py
import importlib
def test_router_back_next_enables_and_moves(monkeypatch):
    app = importlib.import_module("app")
    # initialize idx
    if "current_screen_idx" in app.st.session_state:
        del app.st.session_state["current_screen_idx"]
    assert app._get_idx() == 0
    app._set_idx(1)
    assert app._get_idx() == 1
    app._set_idx(0)
    assert app._get_idx() == 0
