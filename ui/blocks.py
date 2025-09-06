# ui/blocks.py
import streamlit as st

def _inject_nav_css():
    if st.session_state.get("_nav_css_injected"):
        return
    st.markdown(
        """
        <style>
          /* Wrap row so we can style only our nav buttons */
          .nav-row { display: flex; align-items: center; width: 100%; }
          .nav-left, .nav-center, .nav-right { flex: 1 1 0; display: flex; align-items: center; }
          .nav-left  { justify-content: flex-start; }
          .nav-center{ justify-content: center; } /* <-- Reset centered */
          .nav-right { justify-content: flex-end; }

          /* Stable button sizing regardless of viewport width */
          .nav-row .stButton>button {
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
    Returns (back_clicked, reset_clicked, next_clicked)
    - Reset is centered; Back left; Next right
    - Next disabled if valid_to_proceed is False
    - Button sizes remain stable via CSS
    """
    _inject_nav_css()
    st.markdown('<div class="nav-row">', unsafe_allow_html=True)
    # Left: Back
    with st.container():
        st.markdown('<div class="nav-left">', unsafe_allow_html=True)
        back_clicked = st.button("← Back", key="nav_back")
        st.markdown("</div>", unsafe_allow_html=True)
    # Center: Reset
    with st.container():
        st.markdown('<div class="nav-center">', unsafe_allow_html=True)
        reset_clicked = st.button("Reset", key="nav_reset")
        st.markdown("</div>", unsafe_allow_html=True)
    # Right: Next
    with st.container():
        st.markdown('<div class="nav-right">', unsafe_allow_html=True)
        next_clicked = st.button("Next →", disabled=not valid_to_proceed, key="nav_next")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return back_clicked, reset_clicked, next_clicked

# Back-compat for any older imports
def nav_back_next(valid_to_proceed: bool) -> tuple[bool, bool]:
    back, _reset, nxt = nav_back_reset_next(valid_to_proceed)
    return back, nxt
