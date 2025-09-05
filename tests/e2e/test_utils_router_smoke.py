"""
tests/e2e/test_utils_router_smoke.py
Integration-style check: resolve_renderer executes a discovered callable.
"""

from pathlib import Path
import sys
from utils.router import resolve_renderer

def test_router_executes_callable(tmp_path: Path):
    pkg = tmp_path / "spkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "smod.py").write_text("CALLED = {'v': False}\n"
                                 "def render():\n"
                                 "    CALLED['v'] = True\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    fn = resolve_renderer("spkg.smod")
    fn()
    # Read back the module to confirm side-effect
    import importlib
    m = importlib.import_module("spkg.smod")
    assert m.CALLED["v"] is True
