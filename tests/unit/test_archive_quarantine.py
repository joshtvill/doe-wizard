# tests/unit/test_archive_quarantine.py
"""
Archive quarantine:
- /archive/ exists at the repo root.
- It is not importable (kept out of sys.path/packages and has no __init__.py).
- Pytest will not recurse into /archive/.
"""

from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / "archive"

def test_archive_directory_exists():
    assert ARCHIVE_DIR.exists(), "Expected an /archive/ directory at repo root."

def test_archive_not_importable():
    spec = importlib.util.find_spec("archive")
    assert spec is None, (
        "archive/ should NOT be importable. "
        "Ensure it has no __init__.py and is not added to sys.path."
    )
