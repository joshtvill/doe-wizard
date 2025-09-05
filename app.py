# app.py
# ============================================================
# DOE Wizard — App Router (Screens 1–6)
# Thin shell: config, init, pages list, route.
# get_pages() -> list of (key, title, module_name)
# _import_and_render(module_name, call=None) for router unit tests.
# ============================================================

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import os
import streamlit as st

from utils.router import resolve_renderer
from utils.app_init import ensure_artifacts_dir, init_session_state, header

APP_VERSION = "0.1.0"
ARTIFACTS_DIR = Path("artifacts")
IMPORT_ONLY = os.getenv("DOE_WIZARD_APP_IMPORT_ONLY") == "1"

if not IMPORT_ONLY:
    st.set_page_config(
        page_title="DOE Wizard",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )

def get_pages() -> List[Tuple[str, str, str]]:
    """
    Return page registry as a list of 3-tuples:
      (key_lowercase, human_title, module_name)
    """
    return [
        ("session_setup",      "Session Setup",          "screens.session_setup"),
        ("files_join_profile", "Files · Join · Profile", "screens.files_join_profile"),
        ("roles_collapse",     "Roles & Collapse",       "screens.roles_collapse"),
        ("modeling",           "Modeling",               "screens.modeling"),
        ("optimization",       "Optimization",           "screens.optimization"),
        ("handoff",            "Handoff",                "screens.handoff"),
    ]

def _import_and_render(module_name: str, call: Optional[bool] = None) -> bool:
    """
    Test-friendly adapter:
      - Always import and resolve a renderer for `module_name`.
      - If `call` is True, invoke the renderer.
      - If `call` is None, default to NOT calling in import-only mode,
        and calling in interactive mode.
      - Returns True on successful import/resolve (and optional call).
    """
    renderer = resolve_renderer(module_name)
    # Default behavior: avoid calling during import-only test runs
    if call is None:
        call = not IMPORT_ONLY
    if call:
        renderer()  # may raise; let tests see real exceptions if any
    return True

def main() -> None:
    ensure_artifacts_dir(ARTIFACTS_DIR)
    init_session_state(APP_VERSION, ARTIFACTS_DIR)

    if IMPORT_ONLY:
        # Import-only path for router unit tests
        return

    pages: List[Tuple[str, str, str]] = get_pages()
    keys_in_order = [k for (k, _, _) in pages]
    titles_in_order = [t for (_, t, _) in pages]
    module_for_key: Dict[str, str] = {k: m for (k, _, m) in pages}
    title_for_key: Dict[str, str] = {k: t for (k, t, _) in pages}

    with st.sidebar:
        st.markdown("### DOE Wizard")
        st.caption(f"App version: {APP_VERSION}")
        st.divider()
        current_key = st.session_state.get("current_page", keys_in_order[0])
        default_idx = keys_in_order.index(current_key) if current_key in keys_in_order else 0
        choice_title = st.radio("Navigate", titles_in_order, index=default_idx, key="nav_radio")
        choice_key = next(k for k, t in title_for_key.items() if t == choice_title)
        st.divider()
        st.caption(f"Artifacts directory: `{ARTIFACTS_DIR}`")

    # Track nav (non-widget keys only)
    st.session_state["last_page"] = st.session_state.get("current_page", choice_key)
    st.session_state["current_page"] = choice_key

    header(f"DOE Wizard — {title_for_key[choice_key]}", APP_VERSION)

    # Resolve and call renderer at runtime
    module_name = module_for_key[choice_key]
    renderer = resolve_renderer(module_name)

    try:
        renderer()
    except Exception as e:
        st.exception(e)

    st.markdown(
        "<hr style='opacity:0.3;'/>"
        "<div style='font-size:0.9em;opacity:0.8;'>"
        "Screens are thin; business logic lives in services/ & utils/. "
        "Artifacts are written under <code>artifacts/</code> with UTC + local timestamps."
        "</div>",
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
