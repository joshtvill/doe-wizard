# screens/files_join_profile.py
from __future__ import annotations

from pathlib import Path
import json
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st

from ui.blocks import status
from services.artifacts import ARTIFACTS_DIR, write_json
from services.session import get_active_slug

MAX_PREVIEW_ROWS = 1000


def _artifact(slug: str, suffix: str) -> Path:
    return ARTIFACTS_DIR / f"{slug}_{suffix}"


def _read_csv(uploaded) -> pd.DataFrame:
    return pd.read_csv(uploaded)


def _profile_columns(df: pd.DataFrame) -> dict:
    cols = []
    for c in df.columns:
        s = df[c]
        entry = {
            "name": str(c),
            "dtype": str(s.dtype),
            "missing_count": int(s.isna().sum()),
            "missing_pct": float((s.isna().mean() * 100.0) if len(s) else 0.0),
        }
        if pd.api.types.is_numeric_dtype(s):
            sample = s.dropna()
            if len(sample):
                entry.update({
                    "numeric_min_sample": float(sample.min()),
                    "numeric_max_sample": float(sample.max()),
                    "numeric_mean_sample": float(sample.mean()),
                    "numeric_std_sample": float(sample.std(ddof=0)),
                })
        cols.append(entry)
    return {
        "table": {
            "n_rows": int(df.shape[0]),
            "n_cols": int(df.shape[1]),
            "memory_mb_approx": float(df.memory_usage(deep=True).sum() / (1024 ** 2)),
            "sample_rows_used": int(min(len(df), MAX_PREVIEW_ROWS)),
        },
        "columns": cols,
    }


def _join_two(df_left: pd.DataFrame, df_right: pd.DataFrame,
              left_key: str, right_key: str, how: str) -> pd.DataFrame:
    return df_left.merge(df_right, left_on=left_key, right_on=right_key, how=how)


def render():
    st.subheader("Screen 2 — Files / Join / Profile")

    # 1) Resolve active slug every render; bail fast if missing
    active_slug = get_active_slug()
    if not active_slug:
        status("No active session. Please complete Screen 1 (Session Setup) first.", "warn")
        st.stop()

    st.caption(f"Session: `{active_slug}`")

    # 2) If slug changed since last run, clear this screen's per-slug widget state and rerun
    prev_slug_key = "s2_prev_slug"
    prev_slug = st.session_state.get(prev_slug_key)
    if prev_slug != active_slug:
        # Clear only Screen 2 keys; scope by prefix and/or slug
        for k in list(st.session_state.keys()):
            if k.startswith("s2_"):
                del st.session_state[k]
        st.session_state[prev_slug_key] = active_slug
        st.rerun()

    # 3) Uploads (keys scoped to s2_ to avoid collisions)
    c1, c2 = st.columns(2)
    with c1:
        up_left = st.file_uploader("Primary CSV", type=["csv"], key="s2_left")
    with c2:
        up_right = st.file_uploader("Secondary CSV (optional)", type=["csv"], key="s2_right")

    # 4) If two uploads, present join controls in the requested L-M-R layout
    join_params = {}
    if up_left is not None and up_right is not None:
        # read heads for key lists (small nrows)
        try:
            df_l_head = pd.read_csv(up_left, nrows=50)
            up_left.seek(0)
        except Exception as e:
            status(f"Failed reading primary CSV for keys: {e}", "error")
            st.stop()
        try:
            df_r_head = pd.read_csv(up_right, nrows=50)
            up_right.seek(0)
        except Exception as e:
            status(f"Failed reading secondary CSV for keys: {e}", "error")
            st.stop()

        # Keys are per-slug so switching sessions doesn't leak selections
        key_left = f"s2_{active_slug}_left_key"
        key_right = f"s2_{active_slug}_right_key"
        key_how = f"s2_{active_slug}_how"

        cL, cM, cR = st.columns([1, 1, 1])
        with cL:
            left_key = st.selectbox("Join key (left)", list(df_l_head.columns), key=key_left)
        with cM:
            right_key = st.selectbox("Join key (right)", list(df_r_head.columns), key=key_right)
        with cR:
            how = st.selectbox("Join type", ["inner", "left", "right", "outer"], index=0, key=key_how)

        join_params = {"left_key": left_key, "right_key": right_key, "how": how}

    do_exec = st.button("Execute", key="s2_exec")

    if not do_exec:
        st.stop()

    # 5) Execute read/join
    try:
        if up_left is None:
            status("Please upload at least one CSV.", "warn")
            st.stop()

        df_left = _read_csv(up_left)

        if up_right is not None and join_params:
            df_right = _read_csv(up_right)
            df_merged = _join_two(df_left, df_right, **join_params)
        else:
            df_merged = df_left

    except Exception as e:
        status(f"Failed to read/join CSVs: {e}", "error")
        st.stop()

    # 6) Preview + write artifacts using the canonical slug (no new timestamps)
    try:
        preview = df_merged.head(MAX_PREVIEW_ROWS)
        preview_path = _artifact(active_slug, "merged_preview.csv")
        profile_path = _artifact(active_slug, "merged_profile.json")

        # Write files
        preview.to_csv(preview_path, index=False)
        write_json(_profile_columns(df_merged), profile_path)

    except Exception as e:
        status(f"Failed to write artifacts: {e}", "error")
        st.stop()

    # 7) UI feedback + filenames (kept at top-of-preview per your preference)
    st.success("Artifacts saved.")
    st.write(f"**Preview CSV:** `{preview_path}`")
    st.write(f"**Profile JSON:** `{profile_path}`")

    st.dataframe(preview, use_container_width=True)
