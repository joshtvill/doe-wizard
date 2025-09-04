# services/joiner.py
"""
Join service (Mode A minimal)
-----------------------------
Left-join Features and Response tables by user-selected key pairs and return:
- merged_df: pandas.DataFrame
- diagnostics: dict with minimal, screen-2-aligned fields

Diagnostics keys:
- join_type: "left"
- left_rows: int
- right_rows: int
- matched_left_rows: int        # DISTINCT left rows that matched ≥1 right row
- join_rate: float               # matched_left_rows / left_rows
- left_only: int                 # left rows with no match
- right_only: int                # unique right key combos not matched by any left (approx)
- dup_key_left: int              # count of LEFT rows participating in duplicated key combos
- dup_key_right: int             # count of RIGHT rows participating in duplicated key combos
- right_cols_added: int          # number of non-key columns pulled from response
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import pandas as pd


KeyPairs = Sequence[Tuple[str, str]]


class JoinerError(ValueError):
    """Raised for user/actionable join configuration errors."""


def _validate_inputs(
    features_df: pd.DataFrame,
    response_df: pd.DataFrame,
    key_pairs: KeyPairs,
) -> Tuple[List[str], List[str]]:
    if features_df is None or response_df is None:
        raise JoinerError("Both features_df and response_df are required for joining.")

    if not isinstance(key_pairs, (list, tuple)) or len(key_pairs) == 0:
        raise JoinerError("key_pairs must be a non-empty sequence of (left_col, right_col).")

    left_keys: List[str] = []
    right_keys: List[str] = []

    for i, pair in enumerate(key_pairs, start=1):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise JoinerError(f"key_pairs element #{i} must be a 2-tuple of (left_col, right_col).")
        l, r = pair
        if not isinstance(l, str) or not isinstance(r, str) or not l or not r:
            raise JoinerError(f"key_pairs element #{i} has invalid column names: {pair!r}")
        if l not in features_df.columns:
            raise JoinerError(f"Left key '{l}' not found in features_df columns.")
        if r not in response_df.columns:
            raise JoinerError(f"Right key '{r}' not found in response_df columns.")
        left_keys.append(l)
        right_keys.append(r)

    return left_keys, right_keys


def left_join(
    features_df: pd.DataFrame,
    response_df: pd.DataFrame,
    key_pairs: KeyPairs,
    *,
    response_suffix: str = "_resp",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Perform a left join of features_df with response_df using key_pairs.

    Returns
    -------
    (merged_df, diagnostics) : (pd.DataFrame, dict)
    """
    left_keys, right_keys = _validate_inputs(features_df, response_df, key_pairs)

    left_rows = int(len(features_df))
    right_rows = int(len(response_df))

    dup_key_left = int(features_df.duplicated(subset=left_keys, keep=False).sum()) if left_keys else 0
    dup_key_right = int(response_df.duplicated(subset=right_keys, keep=False).sum()) if right_keys else 0

    unique_right_keys = (
        response_df[right_keys].drop_duplicates()
        if right_keys
        else pd.DataFrame({"__dummy__": []})
    )

    # Carry a unique left-row id through the merge so we can count DISTINCT matched left rows
    left_with_id = features_df.copy()
    _ID = "__left_row_id__"
    while _ID in left_with_id.columns:
        _ID += "_"  # extremely unlikely, but guarantee uniqueness
    left_with_id[_ID] = range(len(left_with_id))

    merged = pd.merge(
        left_with_id,
        response_df,
        how="left",
        left_on=left_keys,
        right_on=right_keys,
        suffixes=("", response_suffix),
        indicator=True,
    )

    # Count distinct left rows that matched at least one right row
    matched_left_rows = int(
        merged.loc[merged["_merge"] == "both", _ID].nunique()
    )
    # Left-only rows are those left rows that never matched (count on a per-left-row basis)
    matched_left_ids = set(merged.loc[merged["_merge"] == "both", _ID].unique().tolist())
    left_only = int(left_rows - len(matched_left_ids))

    # Approximate right_only: unique right key combos that never appear in left
    if left_keys:
        left_unique_keys = features_df[left_keys].drop_duplicates()
        right_as_left_named = unique_right_keys.copy()
        right_as_left_named.columns = left_keys
        right_only = int(
            len(
                pd.merge(
                    right_as_left_named,
                    left_unique_keys,
                    how="left",
                    on=left_keys,
                    indicator=True,
                ).query('_merge == "left_only"')
            )
        )
    else:
        right_only = 0

    right_nonkey_cols: List[str] = [c for c in response_df.columns if c not in set(right_keys)]
    right_cols_added = len(right_nonkey_cols)

    # Drop helper cols for cleanliness
    merged = merged.drop(columns=["_merge", _ID])

    diagnostics: Dict[str, object] = {
        "join_type": "left",
        "left_rows": left_rows,
        "right_rows": right_rows,
        "matched_left_rows": matched_left_rows,
        "join_rate": float(matched_left_rows / left_rows) if left_rows > 0 else 0.0,
        "left_only": left_only,
        "right_only": right_only,
        "dup_key_left": dup_key_left,
        "dup_key_right": dup_key_right,
        "right_cols_added": right_cols_added,
    }

    return merged, diagnostics
