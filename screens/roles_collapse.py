import streamlit as st
from services import s3_adapter

def render(df_columns: list[str] | None = None) -> dict:
    st.header("Roles & Collapse (S3)")
    df_columns = df_columns or ["x1", "x2", "x3", "y"]
    candidates = s3_adapter.candidate_role_columns(df_columns)

    responses = st.multiselect("Responses", options=df_columns, default=["y"] if "y" in df_columns else [])
    roles = {"responses": responses}

    ok, errs = s3_adapter.validate_roles(roles)
    if errs: st.info(" • " + "\n • ".join(errs))

    st.caption(f"Candidate factor columns: {', '.join(candidates) or '(none)'}")
    return {"valid_to_proceed": ok, "payload": {"roles": roles, "candidates": candidates}}
