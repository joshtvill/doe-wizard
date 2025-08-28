import streamlit as st

def single_click_button(label, key):
    return st.button(label, key=key, use_container_width=True)

def nav_bar(back=True, reset=True, next=True):
    cols = st.columns(3)
    clicked = {'back': False, 'reset': False, 'next': False}
    if back:
        clicked['back'] = cols[0].button('Back', key='nav_back', use_container_width=True)
    if reset:
        clicked['reset'] = cols[1].button('Reset', key='nav_reset', use_container_width=True)
    if next:
        clicked['next'] = cols[2].button('Next', key='nav_next', use_container_width=True)
    return clicked

def status(msg, level='info'):
    if level == 'error':
        st.error(msg)
    elif level == 'warning':
        st.warning(msg)
    elif level == 'success':
        st.success(msg)
    else:
        st.info(msg)
