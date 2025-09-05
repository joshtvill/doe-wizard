"""
utils/runtime.py
----------------
Project-agnostic runtime helpers used by screens and services.
"""

from __future__ import annotations
import os
from datetime import datetime


def env_flag(name: str) -> bool:
    """Return True iff the environment variable is exactly '1' (trimmed)."""
    return os.environ.get(name, "").strip() == "1"


def session_slug(default: str = "dev") -> str:
    """
    Read the session slug from env if provided, else return default.
    Screens may override with st.session_state later.
    """
    return os.environ.get("DOE_WIZARD_SLUG") or default


def now_utc_iso() -> str:
    """UTC timestamp in ISO-8601 without microseconds, with 'Z' suffix."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
