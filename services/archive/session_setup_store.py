"""
services/session_setup_store.py

Functionality-focused module: persistence for *Session Setup* artifacts only.

Why these functions belong together
-----------------------------------
- Single artifact type: <session_slug>-session-setup.json (contract v3; hyphenated)
- Shared schema + naming convention
- Pure persistence (I/O); no UI or Streamlit state

Public API (≤5 functions)
-------------------------
save_new_session_setup(context: str, objective: str, response: str) -> tuple[str, str]
discover_session_setups(limit: int | None = None) -> list[tuple[str, str, str]]
load_session_setup(slug: str) -> dict

Notes
-----
- Contract v3 naming: '<session_slug>-session-setup.json' (hyphen between slug and artifact)
- 'session_slug' already includes date; never prepend another datetime.
- Artifacts live directly under artifacts/ (no subfolders)
"""

from __future__ import annotations

import os
import json
import glob
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any

# Dependency: your existing slug helper must return a dash-separated slug with a date prefix.
# Example: '250829-cmp-pilot-maximize-mrr'
from utils.naming import session_slug

# Constants (kept local to this functionality)
ARTIFACTS_DIR = "artifacts"
ARTIFACT_SUFFIX = "-session-setup.json"  # contract v3

# Ensure target directory exists
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def save_new_session_setup(context: str, objective: str, response: str) -> tuple[str, str]:
    """
    Persist a new Session Setup JSON using contract v3 naming:
      <session_slug>-session-setup.json

    Returns
    -------
    (slug, path):
      slug : canonical session slug (includes date; dash-separated)
      path : relative path to saved JSON under 'artifacts/'
    """
    slug = session_slug(context, objective, response)  # includes date; no extra datetime here
    path = _session_setup_path(slug)

    payload = {
        "schema_version": "v3",
        "session_slug": slug,
        "context": context,
        "objective": objective,
        "response": response,
        # convenience timestamps
        "datetime_local": datetime.now().isoformat(),
        "datetime_utc": datetime.utcnow().isoformat(),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return slug, path


def discover_session_setups(limit: int | None = None) -> list[tuple[str, str, str]]:
    """
    Discover saved Session Setup JSONs and return:
      [(slug, path, mtime_iso_utc), ...] sorted newest → oldest.

    Contract v3 pattern: '<session_slug>-session-setup.json'
    """
    pattern = os.path.join(ARTIFACTS_DIR, f"*{ARTIFACT_SUFFIX}")
    paths = glob.glob(pattern)
    results: list[tuple[str, str, str]] = []

    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            slug = data.get("session_slug")

            if not slug:
                # Fallback to filename if JSON is missing slug (legacy/hand-edited file)
                base = os.path.basename(p)
                slug = base[: -len(ARTIFACT_SUFFIX)] if base.endswith(ARTIFACT_SUFFIX) else base

            mtime = os.path.getmtime(p)
            mtime_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            results.append((slug, p, mtime_iso))
        except Exception:
            # Discovery is resilient: skip unreadable/malformed files
            continue

    # Sort newest → oldest by modification time (ISO timestamps are sortable)
    results.sort(key=lambda t: t[2], reverse=True)

    return results[:limit] if (limit is not None and limit >= 0) else results


def load_session_setup(slug: str) -> Dict[str, Any]:
    """
    Load a Session Setup JSON by its session slug.

    Parameters
    ----------
    slug : str
        A canonical session slug (e.g., '250829-cmp-pilot-maximize-mrr').

    Returns
    -------
    dict
        Parsed JSON payload.

    Raises
    ------
    FileNotFoundError
        If the artifact does not exist for the provided slug.
    json.JSONDecodeError
        If the file exists but is not valid JSON.
    """
    path = _session_setup_path(slug)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Session setup not found for slug: {slug} at {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------
# Internal helper (private API)
# ----------------------------

def _session_setup_path(slug: str) -> str:
    """Build '<artifacts>/<session_slug>-session-setup.json' (contract v3)."""
    fname = f"{slug}{ARTIFACT_SUFFIX}"
    return os.path.join(ARTIFACTS_DIR, fname)


__all__ = [
    "save_new_session_setup",
    "discover_session_setups",
    "load_session_setup",
]
