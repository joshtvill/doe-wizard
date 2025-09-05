# ui/blocks.py
import streamlit as st

# one-time CSS injector
def _inject_nav_css():
    if st.session_state.get("_nav_css_injected"):
        return
    st.markdown(
        """
        <style>
        /* Keep nav buttons a stable size regardless of viewport */
        .nav-row button {
            min-width: 120px;
            max-width: 120px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_nav_css_injected"] = True

def nav_back_reset_next(valid_to_proceed: bool) -> tuple[bool, bool, bool]:
    """
    Returns (back_clicked, reset_clicked, next_clicked)
    - Next is disabled when valid_to_proceed is False
    - Buttons rendered with consistent width using CSS
    """
    _inject_nav_css()

    st.markdown('<div class="nav-row">', unsafe_allow_html=True)
    # Layout: [spacer][Back][Reset][spacer-grow][Next][spacer]
    cols = st.columns([1, 1, 1, 8, 1, 1])
    with cols[1]:
        back_clicked = st.button("← Back", use_container_width=True, key="nav_back")
    with cols[2]:
        reset_clicked = st.button("Reset", use_container_width=True, key="nav_reset")
    with cols[4]:
        next_clicked = st.button("Next →", disabled=not valid_to_proceed, use_container_width=True, key="nav_next")
    st.markdown("</div>", unsafe_allow_html=True)
    return back_clicked, reset_clicked, next_clicked

# Back-compat if any caller still imports the old name
def nav_back_next(valid_to_proceed: bool) -> tuple[bool, bool]:
    back, _reset, nxt = nav_back_reset_next(valid_to_proceed)
    return back, nxt
