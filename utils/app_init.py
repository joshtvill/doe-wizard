# utils/app_init.py
# Centralized init helpers to keep app.py clean.

from __future__ import annotations
from pathlib import Path
from typing import Optional
from datetime import datetime
import streamlit as st

def ensure_artifacts_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def init_session_state(app_version: str, artifacts_dir: Path) -> None:
    """
    Initialize only non-widget keys. Do NOT mutate widget-bound keys here.
    """
    ss = st.session_state
    ss.setdefault("app_version", app_version)
    ss.setdefault("artifacts_dir", str(artifacts_dir))
    ss.setdefault("current_page", "Session Setup")
    ss.setdefault("last_page", "Session Setup")
    # Preserve existing slug if present
    ss.setdefault("session_slug", ss.get("session_slug", None))

def header(title: str, version: str) -> None:
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<h2 style='margin:0;'>{title}</h2>"
        f"<span style='opacity:0.7;'>v{version}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
