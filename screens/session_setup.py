# screens/session_setup.py
import streamlit as st
from services import s1_adapter

def render() -> dict:
    st.header("Session Setup (S1)")
    name = st.text_input("Session Title", key="s1_title")
    objective = st.radio("Objective", ["Maximize", "Minimize"], index=0, key="s1_objective")
    response_type = st.radio("Response Type", ["Continuous", "Categorical"], index=0, key="s1_response_type")
    context_tag = st.text_input("Context Tag", key="s1_context_tag")
    response_metric = st.text_input("Response Metric", key="s1_response_metric")
    notes = st.text_area("Notes (optional)", key="s1_notes")

    ok, errs = s1_adapter.validate_session_inputs(name, objective, response_type, context_tag, response_metric)
    if errs:
        st.info(" • " + "\n • ".join(errs))

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
            # Declare which session_state keys this screen owns, so Reset can clear them only
            "reset_keys": [
                "s1_title",
                "s1_objective",
                "s1_response_type",
                "s1_context_tag",
                "s1_response_metric",
                "s1_notes",
            ],
        },
    }
