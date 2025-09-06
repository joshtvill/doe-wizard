# tests/unit/test_phase0_guardrails.py
"""
Phase 1+ guardrails (static across remaining phases):
- AST guard: each screens/*.py must define exactly one function named 'render'
- Disk-write guard: fail if any screens/*.py writes to disk (.to_csv(, json.dump(), etc.)

Notes:
- Only checks top-level screens/*.py (not screens/archive/*).

Background (Phase 0 history, now removed):
- Phase 0 had a grandfathering rule that allowed all screens except modeling.py.
- Action for Phase 1 was to remove grandfathering and enforce across all screens.
"""

from __future__ import annotations
import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENS_DIR = REPO_ROOT / "screens"

FORBIDDEN_WRITE_PATTERNS = [
    r"\.to_csv\s*\(",      # pandas CSV writes
    r"json\.dump\s*\(",    # json.dump(
]

def _iter_top_level_screen_py() -> list[Path]:
    """Return top-level screens/*.py files (exclude subdirs like screens/archive/*)."""
    if not SCREENS_DIR.exists():
        return []
    return [p.resolve() for p in SCREENS_DIR.glob("*.py") if p.is_file()]

def test_ast_guard_exactly_one_render_function_in_each_screen():
    """
    Enforce the spine contract: every screen is a thin orchestrator that exposes exactly
    one function named 'render' (and no other defs).
    """
    offenders = []

    for py in _iter_top_level_screen_py():
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            offenders.append((py, f"SyntaxError: {e}"))
            continue

        fn_defs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        names = [f.name for f in fn_defs]
        if names != ["render"]:
            offenders.append((py, f"functions found: {names!r} (expected ['render'])"))

    assert not offenders, (
        "Each screens/*.py must define exactly one function named 'render' (and no others):\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
    )

def test_disk_write_guard_no_writes_in_screens():
    """
    Screens must not write to disk directly (all persistence must route via services/artifacts.py,
    invoked by orchestration code outside of screens). This blocks common write patterns.
    """
    offenders = []

    for py in _iter_top_level_screen_py():
        text = py.read_text(encoding="utf-8")
        for pat in FORBIDDEN_WRITE_PATTERNS:
            if re.search(pat, text):
                offenders.append((py, f"matches pattern: {pat}"))

    assert not offenders, (
        "Screens must not write to disk directly (use services/artifacts.py). "
        "Found potential writes in:\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
    )
