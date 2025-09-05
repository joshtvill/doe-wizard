import streamlit as st

def nav_back_next(valid_to_proceed: bool) -> tuple[bool, bool]:
    cols = st.columns([1, 1, 8, 1, 1])
    with cols[1]:
        prev_clicked = st.button("← Back", use_container_width=True)
    with cols[3]:
        next_clicked = st.button("Next →", disabled=not valid_to_proceed, use_container_width=True)
    return prev_clicked, next_clicked
