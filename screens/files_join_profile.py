import streamlit as st
from services import s2_adapter

def render() -> dict:
    st.header("Files · Join · Profile (S2)")
    # Phase 1 minimal widgets (no file handling yet)
    features_loaded = st.checkbox("Features CSV loaded (stub)", value=True)
    response_loaded = st.checkbox("Response CSV loaded (stub)", value=False)

    ok_files, errs = s2_adapter.validate_files(features_loaded, response_loaded)
    if errs: st.info(" • " + "\n • ".join(errs))

    # In real S2, you would compute join keys and profile previews; Phase 1 keep simple
    return {
        "valid_to_proceed": ok_files,
        "payload": {
            "features_loaded": features_loaded,
            "response_loaded": response_loaded,
            "reset_keys": [
                # every widget key on this screen
                "s2_features_loaded",
                "s2_response_loaded",
            ],
            "reset_defaults": {
                # match the initial defaults used by the widgets above
                "s2_features_loaded": True,
                "s2_response_loaded": False,
            },
        },
    }
