import streamlit as st
from services import s6_adapter

def render() -> dict:
    st.header("Handoff (S6) — Phase 1 stub")
    ok, errs = s6_adapter.ready_stub()
    if errs: st.info(" • " + "\n • ".join(errs))
    return {
        "valid_to_proceed": ok,
        "payload": {
            # no user widgets on this screen yet
            "reset_keys": [],
            # no defaults required
            "reset_defaults": {},
        },
    }
