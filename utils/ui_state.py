# utils/ui_state.py
from __future__ import annotations
from typing import Iterable
import streamlit as st

def bump_version(key: str) -> int:
    """Increment an integer version in session_state and return it."""
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1
    return st.session_state[key]

def clear_keys(keys: Iterable[str]) -> None:
    """Safely clear multiple keys if they exist."""
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = None
