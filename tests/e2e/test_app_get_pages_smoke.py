"""
tests/e2e/test_app_get_pages_smoke.py
Normalizes app.get_pages() so the test works whether it returns:
- a dict[label -> renderer callable], OR
- a list of (key, title, module_name) triples (renderer resolved at runtime), OR
- a list of (label, module_name, renderer) triples (legacy).
"""

import importlib
import os
from typing import Any, Callable, Dict, List, Tuple

from utils.router import resolve_renderer


def _normalize_pages(pages: Any) -> Dict[str, Callable[[], None]]:
    """
    Normalize to {label/title -> renderer callable}.
    Accepts:
      - dict[str, callable]
      - list[tuple] of length 3:
         * (key, title, module_name:str)  -> label = title; resolve renderer via module_name
         * (label, module_name:str, renderer:callable) -> label = label; use renderer
    """
    # Case 1: already a dict[label -> renderer]
    if isinstance(pages, dict):
        normalized: Dict[str, Callable[[], None]] = {}
        for label, maybe_renderer in pages.items():
            if callable(maybe_renderer):
                normalized[label] = maybe_renderer
            elif isinstance(maybe_renderer, str):
                # treat as module name
                normalized[label] = resolve_renderer(maybe_renderer)
            else:
                raise AssertionError(f"Unexpected value type in pages dict: {type(maybe_renderer)} for key {label}")
        return normalized

    # Case 2: list of triples
    if isinstance(pages, list):
        normalized: Dict[str, Callable[[], None]] = {}
        for item in pages:
            assert isinstance(item, (tuple, list)) and len(item) == 3, "Expected a 3-tuple/list per page entry"
            a, b, c = item
            # New shape: (key, title, module_name:str)
            if isinstance(c, str):
                label = str(b)  # human title
                normalized[label] = resolve_renderer(c)
            # Legacy shape: (label, module_name:str, renderer:callable)
            elif callable(c):
                label = str(a)  # label is first element
                normalized[label] = c
            else:
                raise AssertionError(f"Unexpected third element in pages triple: {type(c)}")
        return normalized

    raise AssertionError(f"Unexpected pages type: {type(pages)}")


def test_app_exposes_get_pages(monkeypatch):
    monkeypatch.setenv("DOE_WIZARD_APP_IMPORT_ONLY", "1")
    if "app" in importlib.sys.modules:
        del importlib.sys.modules["app"]
    mod = importlib.import_module("app")
    pages = mod.get_pages()

    norm = _normalize_pages(pages)

    assert isinstance(norm, dict) and len(norm) > 0
    # Sanity: labels are strings and renderers are callables
    for label, renderer in norm.items():
        assert isinstance(label, str)
        assert callable(renderer)
