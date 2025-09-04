"""Simple helpers for Streamlit session state."""
import streamlit as st

def get(key, default=None):
    return st.session_state.get(key, default)

def set(key, value):
    st.session_state[key] = value

def ensure(keys_with_defaults):
    for k, v in keys_with_defaults.items():
        st.session_state.setdefault(k, v)
