import pytest

# Phase 1 refit: these tests depended on pre-refit screen internals (I/O, autorun, or helper APIs).
# They are intentionally xfailed for now, to be migrated or removed by Phase 2/4.
# See Issue #123 (legacy_refit tracking).

pytestmark = [
    pytest.mark.legacy_refit,
    pytest.mark.xfail(
        reason="Phase 1 refit: screen internals moved to adapters/services; legacy test to be ported in Phase 2/4. See #123",
        strict=False,
    ),
]

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
