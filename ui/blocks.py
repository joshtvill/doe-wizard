import streamlit as st

def _inject_nav_css():
    if st.session_state.get("_nav_css_injected"):
        return
    st.markdown(
        """
        <style>
          /* Make button widths stable across viewport sizes */
          .nav-btn .stButton>button {
            min-width: 140px;
            max-width: 140px;
            height: 38px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_nav_css_injected"] = True

def nav_back_reset_next(valid_to_proceed: bool) -> tuple[bool, bool, bool]:
    """
    Horizontal layout:
      [ Back ]   [    Reset    ]                         [ Next ]
    Reset is centered; buttons have stable sizes.
    Returns (back_clicked, reset_clicked, next_clicked).
    """
    _inject_nav_css()
    left, center, spacer, right = st.columns([2, 2, 8, 2])

    with left:
        back_clicked = st.container()
        with back_clicked:
            st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
            back_clicked = st.button("← Back", key="nav_back")
            st.markdown('</div>', unsafe_allow_html=True)

    with center:
        reset_clicked = st.container()
        with reset_clicked:
            st.markdown('<div class="nav-btn" style="display:flex;justify-content:center;">', unsafe_allow_html=True)
            reset_clicked = st.button("Reset", key="nav_reset")
            st.markdown('</div>', unsafe_allow_html=True)

    with right:
        next_clicked = st.container()
        with next_clicked:
            st.markdown('<div class="nav-btn" style="display:flex;justify-content:flex-end;">', unsafe_allow_html=True)
            next_clicked = st.button("Next →", key="nav_next", disabled=not valid_to_proceed)
            st.markdown('</div>', unsafe_allow_html=True)

    return bool(back_clicked), bool(reset_clicked), bool(next_clicked)

# Back-compat
def nav_back_next(valid_to_proceed: bool) -> tuple[bool, bool]:
    back, _reset, nxt = nav_back_reset_next(valid_to_proceed)
    return back, nxt
