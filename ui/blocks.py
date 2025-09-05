# ui/blocks.py
"""Shared UI blocks for Streamlit screens (MVP minimal, Arrow-free previews)."""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st
import pandas as pd

# -- internal: safe HTML table to avoid pyarrow dependency in st.dataframe --
def _html_table(df: pd.DataFrame, caption: Optional[str] = None) -> None:
    if caption:
        st.markdown(f"**{caption}**")
    if df is None or df.empty:
        st.info("No data.")
        return
    st.markdown(df.to_html(index=False, border=1), unsafe_allow_html=True)

def app_header(title: str, subtitle: Optional[str] = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def section_header(text: str) -> None:
    st.subheader(text)

def status_zone(messages: List[Dict[str, Any]]) -> None:
    """Each item: {level: 'error'|'warning'|'info'|'success', text: str}"""
    for m in messages:
        lvl = m.get("level", "info")
        txt = m.get("text", "")
        if lvl == "error":
            st.error(txt)
        elif lvl == "warning":
            st.warning(txt)
        elif lvl == "success":
            st.success(txt)
        else:
            st.info(txt)

def table_summary_preview(summary: Dict[str, Any]) -> None:
    if not summary:
        st.info("No summary available.")
        return
    _html_table(pd.DataFrame([summary]), caption="Table-level summary")

def columns_profile_preview(cols: List[Dict[str, Any]]) -> None:
    if not cols:
        st.info("No column profile available.")
        return
    _html_table(pd.DataFrame(cols), caption="Column-level profile")

def table_preview(df: pd.DataFrame, max_rows: int = 100) -> None:
    if df is None or df.empty:
        st.info("No table to preview.")
        return
    _html_table(df.head(max_rows), caption=f"Table preview (first {max_rows} rows)")

def nav_bar(
    back_enabled: bool,
    next_enabled: bool,
    on_back_label: str = "Back",
    on_reset_label: str = "Reset",
    on_next_label: str = "Next",
    cols: Tuple[float, float, float] = (1, 1, 1),
) -> Tuple[bool, bool, bool]:
    """Returns (clicked_back, clicked_reset, clicked_next)."""
    c1, c2, c3 = st.columns(cols)
    with c1:
        clicked_back = st.button(on_back_label, disabled=not back_enabled, use_container_width=True, key="nav_back")
    with c2:
        clicked_reset = st.button(on_reset_label, use_container_width=True, type="secondary", key="nav_reset")
    with c3:
        clicked_next = st.button(on_next_label, disabled=not next_enabled, use_container_width=True, type="primary", key="nav_next")
    return clicked_back, clicked_reset, clicked_next
