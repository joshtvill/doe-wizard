"""
services/artifacts.py
=====================
Thin facade that exposes the same public API but delegates to artifacts_core
for the heavy lifting (paths, atomic writes, hashing, logging).

Public API kept stable:
- write_merged_csv
- write_profile_json
- write_modeling_ready_csv
- write_datacard_json

Back-compat helpers re-exported:
- safe_path, save_json, load_json, save_csv
- compute_roles_signature
"""

from __future__ import annotations
from typing import Any, Dict, Union, Optional
from pathlib import Path
import pandas as pd

# Prefer project constants; fall back to defaults to avoid import errors during early scaffolding.
try:
    from utils.constants import SCHEMA_VERSION
except Exception:
    SCHEMA_VERSION = "2025-08-29"

from .artifacts_core import (
    write_csv_with_log,
    write_json_with_log,
    compute_roles_signature,
    save_json,
    load_json,
    save_csv,
    safe_path,  # <-- re-export to satisfy legacy tests/imports
)

__all__ = [
    # writers
    "write_merged_csv",
    "write_profile_json",
    "write_modeling_ready_csv",
    "write_datacard_json",
    # helpers (back-compat)
    "safe_path",
    "save_json",
    "load_json",
    "save_csv",
    "compute_roles_signature",
]

# ---------- S2 writers ----------

def write_merged_csv(
    df: pd.DataFrame,
    *,
    session_slug: str,
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
) -> Dict[str, Any]:
    """
    Write artifacts/<slug>/merged.csv (canonical merged dataset).
    Returns: {"path", "dataset_hash", "rows", "bytes"}
    """
    result = write_csv_with_log(
        df=df,
        session_slug=session_slug,
        screen="S2",
        artifact_name="merged.csv",
        schema_version=schema_version,
        root=root,
        dataset_hash=None,            # compute after write
    )
    return result


def write_profile_json(
    profile: Dict[str, Any],
    *,
    session_slug: str,
    dataset_hash: str,
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
) -> str:
    """
    Write artifacts/<slug>/profile.json including schema_version + dataset_hash.
    """
    return write_json_with_log(
        payload=profile,
        session_slug=session_slug,
        screen="S2",
        artifact_name="profile.json",
        schema_version=schema_version,
        root=root,
        dataset_hash=dataset_hash,
    )

# ---------- S3 writers ----------

def write_modeling_ready_csv(
    df: pd.DataFrame,
    *,
    session_slug: str,
    dataset_hash: str,
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
) -> Dict[str, Any]:
    """
    Write artifacts/<slug>/modeling_ready.csv and log rows/bytes.
    """
    return write_csv_with_log(
        df=df,
        session_slug=session_slug,
        screen="S3",
        artifact_name="modeling_ready.csv",
        schema_version=schema_version,
        root=root,
        dataset_hash=dataset_hash,
    )


def write_datacard_json(
    datacard: Dict[str, Any],
    *,
    session_slug: str,
    dataset_hash: str,
    roles_signature: str,
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
) -> str:
    """
    Write artifacts/<slug>/datacard.json including schema_version, dataset_hash, roles_signature.
    """
    return write_json_with_log(
        payload=datacard,
        session_slug=session_slug,
        screen="S3",
        artifact_name="datacard.json",
        schema_version=schema_version,
        root=root,
        dataset_hash=dataset_hash,
        roles_signature=roles_signature,
    )
