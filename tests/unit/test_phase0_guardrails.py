# tests/unit/test_phase0_guardrails.py
"""
Phase 0 guardrails (grandfather mode):
- AST guard: fail if any non-grandfathered screens/*.py defines a function
- Disk-write guard: fail if any non-grandfathered screens/*.py writes to disk
  (.to_csv(, json.dump(), etc.)

Grandfathering rule (Phase 0 only):
- Temporarily allow all screens except modeling.py.
- This preserves the "screens are orchestration-only" rule for modeling.py now,
  while letting you defer refactors of the other screens to Phase 1/2.

Action for Phase 1:
- Remove the grandfathering and enforce across all screens.

Notes:
- Only checks top-level screens/*.py (not screens/archive/*).
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

def _grandfather_allowlist() -> set[Path]:
    """
    Phase 0: allow everything except modeling.py.
    This set is computed dynamically from the current tree,
    so you don't need to update it when files change.
    """
    files = _iter_top_level_screen_py()
    allow = set(files)
    # Enforce on modeling.py immediately
    modeling = (SCREENS_DIR / "modeling.py").resolve()
    if modeling in allow:
        allow.remove(modeling)
    return allow

def test_ast_guard_no_functions_in_screens():
    offenders = []
    allow = _grandfather_allowlist()

    for py in _iter_top_level_screen_py():
        if py in allow:
            continue  # grandfathered for Phase 0
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            offenders.append((py, f"SyntaxError: {e}"))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                offenders.append((py, f"function '{node.name}'"))

    assert not offenders, (
        "Screens must be orchestration-only (no function defs) outside the Phase-0 grandfather list.\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
        + "\nPhase 0 note: all screens except modeling.py are temporarily grandfathered.\n"
        "Phase 1: remove grandfathering and enforce on all screens."
    )

def test_disk_write_guard_no_writes_in_screens():
    offenders = []
    allow = _grandfather_allowlist()

    for py in _iter_top_level_screen_py():
        if py in allow:
            continue  # grandfathered for Phase 0
        text = py.read_text(encoding="utf-8")
        for pat in FORBIDDEN_WRITE_PATTERNS:
            if re.search(pat, text):
                offenders.append((py, f"matches pattern: {pat}"))

    assert not offenders, (
        "Screens must not write to disk directly (use services/artifacts.py) "
        "outside the Phase-0 grandfather list.\nFound potential writes in:\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
        + "\nPhase 0 note: all screens except modeling.py are temporarily grandfathered.\n"
        "Phase 1: remove grandfathering and enforce on all screens."
    )
