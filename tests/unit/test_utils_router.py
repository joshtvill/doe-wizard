"""
tests/unit/test_utils_router.py
Validates resolve_renderer() resolves common names and raises at call-time for missing renderers.
"""

from pathlib import Path
import sys
import types
import importlib
import pytest

from utils.router import resolve_renderer

def _make_pkg(tmp_path: Path, pkg: str, mod: str, body: str):
    """Create a temp package/module with given body and add tmp to sys.path."""
    p = tmp_path / pkg
    p.mkdir(parents=True, exist_ok=True)
    (p / "__init__.py").write_text("", encoding="utf-8")
    (p / f"{mod}.py").write_text(body, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))

def test_resolve_renderer_prefers_render(tmp_path: Path, monkeypatch):
    _make_pkg(tmp_path, "tpkg", "m1", "def render():\n    return None\n")
    fn = resolve_renderer("tpkg.m1")
    assert callable(fn)
    fn()  # should not raise

def test_resolve_renderer_falls_back_order(tmp_path: Path):
    # Only render_m2 defined
    _make_pkg(tmp_path, "tpkg2", "m2", "def render_m2():\n    return None\n")
    fn = resolve_renderer("tpkg2.m2")
    assert callable(fn)
    fn()

def test_resolve_renderer_render_screen(tmp_path: Path):
    _make_pkg(tmp_path, "tpkg3", "m3", "def render_screen():\n    return None\n")
    fn = resolve_renderer("tpkg3.m3")
    fn()

def test_resolve_renderer_main(tmp_path: Path):
    _make_pkg(tmp_path, "tpkg4", "m4", "def main():\n    return None\n")
    fn = resolve_renderer("tpkg4.m4")
    fn()

def test_resolve_renderer_missing_raises_on_call(tmp_path: Path):
    _make_pkg(tmp_path, "tpkg5", "m5", "X=1\n")
    fn = resolve_renderer("tpkg5.m5")
    with pytest.raises(RuntimeError):
        fn()
