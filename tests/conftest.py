
# Ensures the project root is on sys.path so imports like `from services...` work.
# Place this file at: <repo>/tests/conftest.py
import sys
from pathlib import Path

# tests/ -> repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
