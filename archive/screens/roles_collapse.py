# screens/roles_collapse.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

import pandas as pd
import streamlit as st

from ui.blocks import status
from services.artifacts import ARTIFACTS_DIR
from services.roles import validate_roles, save_roles_json, Role
from services.session import get_active_slug  # <- Screen 1 is the sole authority


# ---------- artifact helpers ----------

def _artifact(slug: str, suffix: str) -> Path:
    return ARTIFACTS_DIR / f"{slug}_{suffix}"

def _load_columns_for_slug(slug: str) -> List[str]:
    """
    Read columns for the **exact** session slug:
      1) <slug>_merged_preview.csv (header only)
      2) <slug>_merged_profile.json['columns']
    """
    preview_csv = _artifact(slug, "merged_preview.csv")
    if preview_csv.exists():
        try:
            df_head = pd.read_csv(preview_csv, nrows=1)
            cols = list(df_head.columns)
            if cols:
                return cols
        except Exception:
            pass

    profile_json = _artifact(slug, "merged_profile.json")
    if profile_json.exists():
        try:
            with profile_json.open("r", encoding="utf-8") as f:
                prof = json.load(f)
            if isinstance(prof, dict) and isinstance(prof.get("columns"), list):
                return list(prof["columns"])
        except Exception:
            pass

    return []

def _default_role_for_col(col: str) -> Role:
    c = col.lower()
    if c in ("id", "run_id", "wafer_id", "lot_id"):
        return "id"
    if "time" in c or "timestamp" in c or "date" in c:
        return "time"
    return "feature"


# ---------- screen entrypoint ----------

def render():
    st.subheader("Screen 3 — Roles & Collapse (Slice 1: Assign Roles)")

    # Only trust the active slug set by Screen 1
    active_slug = get_active_slug()
    if not active_slug:
        status("No active session. Please go to Screen 1 (Session Setup) to create or load a session.", "warn")
        st.stop()

    st.caption(f"Session: `{active_slug}`")

    # Load columns for this slug only
    cols = _load_columns_for_slug(active_slug)
    if not cols:
        status("No merged table columns found for this session. Complete Screen 2 (Files / Join / Profile) first.", "warn")
        st.stop()

    st.write("Assign a role for each column and **Save**. You need at least one **feature** and one **response**.")

    role_options: List[Role] = ["feature", "response", "id", "time", "ignore"]

    key_prefix = f"roles_{active_slug}_"
    if key_prefix not in st.session_state:
        st.session_state[key_prefix] = {c: _default_role_for_col(c) for c in cols}

    mapping: Dict[str, Role] = st.session_state[key_prefix]

    for c in cols:
        current = mapping.get(c, "feature")
        chosen = st.selectbox(
            label=c,
            options=role_options,
            index=role_options.index(current) if current in role_options else 0,
            key=f"{key_prefix}{c}",
            help="Each column must have exactly one role.",
        )
        mapping[c] = chosen

    st.divider()

    errors = validate_roles(mapping)
    if errors:
        st.error("Validation errors:\n- " + "\n- ".join(errors))

    roles_path = _artifact(active_slug, "roles.json")

    col1, col2 = st.columns([1, 2])
    with col1:
        disabled = len(errors) > 0
        if st.button("Save roles", disabled=disabled):
            save_roles_json(roles_path, active_slug, mapping)
            st.success(f"Saved: {roles_path}")

    with col2:
        can_next = (len(errors) == 0) and roles_path.exists()
        st.button("Next → (Slice 2: Collapse)", disabled=not can_next)
