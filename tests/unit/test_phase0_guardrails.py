# tests/unit/test_phase0_guardrails.py
"""
Phase 0 guardrails:
- AST guard: fail if any non-archive screens/*.py defines a function
- Disk-write guard: fail if any non-archive screens/*.py writes to disk (.to_csv(, json.dump()
Acceptance:
- Tests fail if helpers or writes sneak into screens.
"""

from __future__ import annotations
import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/unit/.. -> repo root
SCREENS_DIR = REPO_ROOT / "screens"
ARCHIVE_SUBDIR = SCREENS_DIR / "archive"

FORBIDDEN_WRITE_PATTERNS = [
    r"\.to_csv\s*\(",      # pandas to CSV
    r"json\.dump\s*\(",    # json.dump(
]

def _iter_non_archive_screen_py() -> list[Path]:
    if not SCREENS_DIR.exists():
        return []
    files = []
    for p in SCREENS_DIR.glob("*.py"):
        # Only top-level screens/*.py (archive is a subdir)
        files.append(p)
    return [p for p in files if p.is_file()]

def test_ast_guard_no_functions_in_screens():
    offenders = []

    for py in _iter_non_archive_screen_py():
        # Parse AST and look for FunctionDef/AsyncFunctionDef
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            offenders.append((py, f"SyntaxError: {e}"))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                offenders.append((py, f"function '{node.name}'"))

    assert not offenders, (
        "Screens must be orchestration-only: found function definitions in:\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
        + "\nMove helpers to services/utils/ui and import from screens instead."
    )

def test_disk_write_guard_no_writes_in_screens():
    offenders = []

    for py in _iter_non_archive_screen_py():
        text = py.read_text(encoding="utf-8")
        for pat in FORBIDDEN_WRITE_PATTERNS:
            if re.search(pat, text):
                offenders.append((py, f"matches pattern: {pat}"))

    assert not offenders, (
        "Screens must not write to disk directly (use services/artifacts.py).\n"
        "Found potential writes in:\n"
        + "\n".join(f" - {path}: {why}" for path, why in offenders)
    )
