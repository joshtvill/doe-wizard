import os
import importlib

def test_app_would_route_to_optimization(monkeypatch):
    # Import-only: don't render Streamlit, just verify the router is callable
    monkeypatch.setenv("DOE_WIZARD_APP_IMPORT_ONLY", "1")
    if "app" in importlib.sys.modules:
        del importlib.sys.modules["app"]
    mod = importlib.import_module("app")

    # Sanity: _import_and_render tries to import the screen module;
    # if present, it optionally calls render(). We only assert it doesn't throw.
    mod._import_and_render("screens.optimization")
