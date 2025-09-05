# services/io.py
from __future__ import annotations
from pathlib import Path
from typing import IO, Optional, Union

import pandas as pd

Src = Union[str, Path, IO]

def _reset_stream(src: Src) -> None:
    # Streamlit's UploadedFile and StringIO have .seek; reset to start before re-reading
    if hasattr(src, "seek"):
        try:
            src.seek(0)
        except Exception:
            pass

def read_csv_safely(src: Src, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Read a CSV with sane defaults and simple encoding fallback.
    Works for:
      - file paths (str/Path)
      - in-memory streams (StringIO/BytesIO)
      - Streamlit UploadedFile objects
    """
    _reset_stream(src)
    try:
        df = pd.read_csv(src, nrows=nrows, low_memory=False)
    except UnicodeDecodeError:
        _reset_stream(src)
        df = pd.read_csv(src, nrows=nrows, low_memory=False, encoding="latin1")
    return df

def sniff_columns(src: Src) -> list[str]:
    """
    Return column names without loading all rows (header-only parse).
    """
    df0 = read_csv_safely(src, nrows=0)
    return [str(c) for c in df0.columns.tolist()]

def join_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_key: str,
    right_key: str,
    how: str = "inner",
) -> pd.DataFrame:
    """
    Lightweight join wrapper with defensive copies and clear errors.
    """
    if left_key not in left.columns:
        raise KeyError(f"Left key '{left_key}' not in left columns.")
    if right_key not in right.columns:
        raise KeyError(f"Right key '{right_key}' not in right columns.")
    L = left.copy()
    R = right.copy()
    return L.merge(R, left_on=left_key, right_on=right_key, how=how)
