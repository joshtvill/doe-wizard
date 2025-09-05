# ui/blocks.py
import streamlit as st

def page_header(title: str, subtitle: str | None = None):
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def status(msg: str, kind: str = "info"):
    kind = kind.lower()
    if kind in ("error", "err"):
        st.error(msg)
    elif kind in ("warn", "warning"):
        st.warning(msg)
    elif kind in ("success", "ok"):
        st.success(msg)
    else:
        st.info(msg)
