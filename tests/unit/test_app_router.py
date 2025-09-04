import os
import importlib

def test_app_import_and_pages(monkeypatch):
    monkeypatch.setenv("DOE_WIZARD_APP_IMPORT_ONLY", "1")
    if "app" in importlib.sys.modules:
        del importlib.sys.modules["app"]
    mod = importlib.import_module("app")
    pages = mod.get_pages()
    keys = [k for (k, _, _) in pages]
    titles = [t for (_, t, _) in pages]
    modules = [m for (_, _, m) in pages]

    assert "optimization" in keys
    assert any("Optimization" in t for t in titles)
    assert "screens.optimization" in modules
