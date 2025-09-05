"""
services/artifacts_core.py
--------------------------------
Core helpers for artifact writers:
- Path safety & session folder
- Atomic writes (text/bytes)
- SHA256 hashing
- Roles signature hashing
- Generic CSV/JSON writers that also append JSONL logs

Used by services/artifacts.py to keep the public API small and readable.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, Union
import hashlib
import json
import os
import tempfile

import pandas as pd

# Prefer project constants; fall back to sane defaults during early scaffolding.
try:
    from utils.constants import ARTIFACTS_DIR, SCHEMA_VERSION
except Exception:
    ARTIFACTS_DIR = "artifacts"
    SCHEMA_VERSION = "2025-08-29"

from utils.logging import log_event  # per-screen JSONL write events


# ---------- paths & atomic ----------

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _root_dir(root: Union[str, Path] = ".") -> Path:
    return Path(root).resolve()

def artifacts_root(root: Union[str, Path] = ".") -> Path:
    return (_root_dir(root) / ARTIFACTS_DIR).resolve()

def session_dir(session_slug: str, root: Union[str, Path] = ".") -> Path:
    d = (artifacts_root(root) / session_slug).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d

def safe_path(filename: str, root: Union[str, Path] = ".") -> Path:
    """
    Back-compat helper used by some tests and legacy callers.
    Behavior:
      - If filename looks like "<slug>_<name>", route to per-slug folder
        artifacts/<slug>/<name>.
      - Otherwise place under artifacts/<filename>.
    Prevents directory escape and ensures parent dirs exist.
    """
    aroot = artifacts_root(root)
    # Detect pattern: <slug>_<name> (no path separators)
    if ("/" not in filename) and ("\\" not in filename) and ("_" in filename):
        parts = filename.split("_", 1)
        slug, rest = parts[0], parts[1]
        candidate = (aroot / slug / rest).resolve()
        if str(candidate).startswith(str(aroot)):
            _ensure_dir(candidate)
            return candidate
    # Fallback: flat under artifacts/
    target = (aroot / filename).resolve()
    if not str(target).startswith(str(aroot)):
        raise ValueError("Unsafe artifact path outside artifacts/")
    _ensure_dir(target)
    return target

def atomic_write_text(path: Path, text: str) -> int:
    _ensure_dir(path)
    with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    if path.exists():
        path.unlink()
    os.replace(tmp_path, path)
    return path.stat().st_size

def atomic_write_bytes(path: Path, data: bytes) -> int:
    _ensure_dir(path)
    with tempfile.NamedTemporaryFile("wb", dir=str(path.parent), delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    if path.exists():
        path.unlink()
    os.replace(tmp_path, path)
    return path.stat().st_size


# ---------- hashing ----------

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def compute_roles_signature(roles_map: Dict[str, Any], collapse_spec: Optional[Dict[str, Any]] = None) -> str:
    """
    Stable signature over role mapping + optional collapse spec (JSON, sorted keys).
    """
    payload = {"roles": roles_map or {}, "collapse": collapse_spec or {}}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ---------- generic writers with logging ----------

def write_csv_with_log(
    *,
    df: pd.DataFrame,
    session_slug: str,
    screen: str,               # "S2", "S3", ...
    artifact_name: str,        # e.g., "merged.csv"
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
    dataset_hash: Optional[str] = None,
    roles_signature: Optional[str] = None,
) -> Dict[str, Any]:
    out = session_dir(session_slug, root) / artifact_name
    rows = int(df.shape[0])
    df.to_csv(out, index=False, encoding="utf-8")
    bytes_ = out.stat().st_size

    # If this is the canonical dataset CSV and no hash provided, compute now.
    if artifact_name == "merged.csv" and dataset_hash is None:
        dataset_hash = sha256_file(out)

    log_event(
        session_slug=session_slug,
        screen=screen,
        event="write_artifact",
        artifact=artifact_name,
        schema_version=schema_version,
        dataset_hash=dataset_hash,
        roles_signature=roles_signature,
        details={"rows": rows, "bytes": bytes_},
    )
    return {"path": str(out), "rows": rows, "bytes": bytes_, "dataset_hash": dataset_hash}

def write_json_with_log(
    *,
    payload: Dict[str, Any],
    session_slug: str,
    screen: str,
    artifact_name: str,         # e.g., "profile.json"
    schema_version: str = SCHEMA_VERSION,
    root: Union[str, Path] = ".",
    dataset_hash: Optional[str] = None,
    roles_signature: Optional[str] = None,
) -> str:
    out = session_dir(session_slug, root) / artifact_name
    body = dict(payload)
    # Ensure schema_version present; carry hashes if provided
    body.setdefault("schema_version", schema_version)
    if dataset_hash is not None:
        body["dataset_hash"] = dataset_hash
    if roles_signature is not None:
        body["roles_signature"] = roles_signature

    size = atomic_write_text(out, json.dumps(body, indent=2))

    log_event(
        session_slug=session_slug,
        screen=screen,
        event="write_artifact",
        artifact=artifact_name,
        schema_version=schema_version,
        dataset_hash=dataset_hash,
        roles_signature=roles_signature,
        details={"bytes": size},
    )
    return str(out)


# ---------- back-compat generic helpers (used by tests/tools) ----------

def save_json(obj: Any, filename: str, root: Union[str, Path] = ".") -> Path:
    p = safe_path(filename, root=root)
    atomic_write_text(p, json.dumps(obj, ensure_ascii=False, indent=2))
    return p

def load_json(filename: str, root: Union[str, Path] = ".") -> Any:
    p = safe_path(filename, root=root)
    return json.loads(p.read_text(encoding="utf-8"))

def save_csv(df: pd.DataFrame, filename: str, root: Union[str, Path] = ".") -> Path:
    p = safe_path(filename, root=root)
    df.to_csv(p, index=False)
    return p
