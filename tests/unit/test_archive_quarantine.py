# tests/unit/test_archive_quarantine.py
"""
Archive quarantine (PEP 420 aware):

We allow 'archive/' to exist at repo root for storage, but enforce:
- No __init__.py under archive/  -> prevents regular packages
- Excluded from packaging        -> won't be distributed
- Optional: it's OK if importlib finds a *namespace* package; that's a Python quirk.
"""

from __future__ import annotations
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / "archive"

def test_archive_directory_exists():
    assert ARCHIVE_DIR.exists(), "Expected an /archive/ directory at repo root."

def test_archive_has_no_init_files_anywhere():
    inits = list(ARCHIVE_DIR.rglob("__init__.py"))
    assert not inits, f"archive/ must not contain __init__.py files; found: {inits}"

def test_archive_not_packaged_and_namespace_is_ok():
    """
    PEP 420 makes bare directories importable as *namespace* packages when the
    repo root is on sys.path. That's OK. What we forbid is shipping 'archive'
    as a regular package.
    """
    spec = importlib.util.find_spec("archive")
    # Accept either not found OR a namespace package (loader None).
    assert spec is None or (spec.loader is None and spec.submodule_search_locations is not None), (
        "archive/ should not be a regular package. If importable, it must be a PEP 420 namespace "
        "package (loader None)."
    )
