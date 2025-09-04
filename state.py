"""
state.py

Central helpers for autoloading latest artifacts and fingerprint comparison.
Non-UI, pure functions used by screens to soft-block when artifacts are stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json

from constants import SCHEMA_VERSION


def _read_json(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def _sha256_file(p: Path) -> Optional[str]:
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def autoload_latest_artifacts(session_slug: str) -> Dict[str, Any]:
    """Discover latest artifacts for a slug and compute upstream/current metadata.

    Returns:
        {
          "paths": {...},
          "upstream": {"dataset_hash": str|None, "roles_signature": str|None, "schema_version": str},
          "current": {"dataset_hash": str|None, "roles_signature": str|None, "schema_version": str|None},
        }
    """
    art = Path("artifacts") / session_slug
    paths = {
        "merged": art / "merged.csv",
        "profile": art / "profile.json",
        "modeling_ready": art / "modeling_ready.csv",
        "datacard": art / "datacard.json",
        "model_compare": art / "model_compare.csv",
        "champion_bundle": art / "champion_bundle.json",
        "opt_settings": art / "optimization_settings.json",
        "opt_trace": art / "optimization_trace.json",
    }

    # Upstream fingerprints
    upstream_ds = _sha256_file(paths["merged"]) if paths["merged"].exists() else None
    datacard = _read_json(paths["datacard"]) or {}
    upstream_roles = datacard.get("roles_signature")

    # Current fingerprint hints from latest JSON artifacts
    profile = _read_json(paths["profile"]) or {}
    bundle = _read_json(paths["champion_bundle"]) or {}
    opt_settings = _read_json(paths["opt_settings"]) or {}
    opt_trace = _read_json(paths["opt_trace"]) or {}

    # Prefer most downstream fingerprints present
    current_ds = (
        opt_settings.get("dataset_hash")
        or opt_trace.get("dataset_hash")
        or bundle.get("dataset_hash")
        or datacard.get("dataset_hash")
        or profile.get("dataset_hash")
    )
    current_roles = (
        opt_settings.get("roles_signature")
        or opt_trace.get("roles_signature")
        or bundle.get("roles_signature")
        or datacard.get("roles_signature")
    )
    current_schema = (
        opt_settings.get("schema_version")
        or opt_trace.get("schema_version")
        or bundle.get("schema_version")
        or datacard.get("schema_version")
        or profile.get("schema_version")
    )

    # HARD schema gate: if current declares a schema_version that differs, raise
    if current_schema and str(current_schema) != str(SCHEMA_VERSION):
        raise RuntimeError(f"schema_version mismatch: expected={SCHEMA_VERSION} current={current_schema}")

    return {
        "paths": {k: str(v) for k, v in paths.items()},
        "upstream": {"dataset_hash": upstream_ds, "roles_signature": upstream_roles, "schema_version": SCHEMA_VERSION},
        "current": {"dataset_hash": current_ds, "roles_signature": current_roles, "schema_version": current_schema},
    }


def fingerprint_check(upstream: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """Compare upstream vs current fingerprints and schema.

    Returns: {"ok": bool, "reasons": list[str]}
    """
    reasons: list[str] = []
    up_ds = upstream.get("dataset_hash")
    up_roles = upstream.get("roles_signature")
    up_schema = upstream.get("schema_version")

    cur_ds = current.get("dataset_hash")
    cur_roles = current.get("roles_signature")
    cur_schema = current.get("schema_version")

    if up_ds and cur_ds and str(up_ds) != str(cur_ds):
        reasons.append("dataset_hash mismatch")
    if up_roles and cur_roles and str(up_roles) != str(cur_roles):
        reasons.append("roles_signature mismatch")
    if up_schema and cur_schema and str(up_schema) != str(cur_schema):
        reasons.append("schema_version mismatch")

    return {"ok": len(reasons) == 0, "reasons": reasons}
