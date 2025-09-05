# services/session.py
from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import json
import streamlit as st
from services.artifacts import ARTIFACTS_DIR

SESSION_KEY = "session_slug"

def get_active_slug() -> Optional[str]:
    slug = st.session_state.get(SESSION_KEY)
    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    return None

def set_active_slug(slug: str) -> None:
    st.session_state[SESSION_KEY] = slug.strip()

def discover_session_slugs() -> List[Tuple[str, float]]:
    """List (slug, mtime) for <slug>_session_setup.json, newest first."""
    if not ARTIFACTS_DIR.exists():
        return []
    pairs: List[Tuple[str, float]] = []
    for p in ARTIFACTS_DIR.glob("*_session_setup.json"):
        try:
            slug = p.name.replace("_session_setup.json", "")
            pairs.append((slug, p.stat().st_mtime))
        except Exception:
            continue
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs

def session_setup_path(slug: str) -> Path:
    return ARTIFACTS_DIR / f"{slug}_session_setup.json"

def load_session_setup(slug: str) -> Optional[Dict[str, Any]]:
    p = session_setup_path(slug)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
