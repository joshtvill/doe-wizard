# screens/session_setup.py
import streamlit as st
from services import s1_adapter

def render() -> dict:
    st.header("Session Setup (S1)")
    name = st.text_input("Session Title")
    objective = st.radio("Objective", ["Maximize", "Minimize"], index=0)
    response_type = st.radio("Response Type", ["Continuous", "Categorical"], index=0)
    context_tag = st.text_input("Context Tag")
    response_metric = st.text_input("Response Metric")
    notes = st.text_area("Notes (optional)")

    ok, errs = s1_adapter.validate_session_inputs(name, objective, response_type, context_tag, response_metric)
    if errs:
        st.info(" • " + "\n • ".join(errs))

    # Contract-accurate session_slug preview
    slug = ""
    if name or context_tag or objective or response_metric:
        slug = s1_adapter.compute_slug(
            project_name=name or "",
            context_tag=context_tag or "",
            objective=objective or "",
            response_metric=response_metric or "",
        )
    if slug:
        st.caption(f"Artifact Prefix preview: {slug}")

    return {
        "valid_to_proceed": ok,
        "payload": {
            "session_title": name,
            "objective": objective,
            "response_type": response_type,
            "context_tag": context_tag,
            "response_metric": response_metric,
            "notes": notes,
            "slug": slug,
        },
    }
