# ui/nav.py
"""
Simple navigation block for screens.
- Renders Back / Next buttons side-by-side (if labels are provided)
- Returns "prev" | "next" | None based on user click
- Does not implement routing itself; the app/router can consume the return value
"""

from __future__ import annotations
from typing import Optional
import streamlit as st


def nav_buttons(
    prev_label: Optional[str] = None,
    next_label: Optional[str] = None,
    key_prefix: str = "nav",
) -> Optional[str]:
    """
    Render Back/Next buttons. Return which one was pressed, or None.

    Example:
      action = nav_buttons("← Back", "Next →", key_prefix="s1")
      if action == "next": ...
    """
    col1, col2 = st.columns(2)
    go_prev = False
    go_next = False

    if prev_label:
        go_prev = col1.button(prev_label, key=f"{key_prefix}_prev")
    if next_label:
        go_next = col2.button(next_label, type="primary", key=f"{key_prefix}_next")

    if go_prev:
        return "prev"
    if go_next:
        return "next"
    return None
