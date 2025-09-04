"""
utils/logging.py
Purpose: Append-only JSONL logger for screen-level artifact write events (S1–S6).
Scope: Called by writers in services/artifacts.py and packaging in services/handoff_packaging.py.

Acceptance:
- Writes line-delimited JSON (.jsonl) under artifacts/<session_slug>/screenX_log.jsonl
- Adds both UTC and local timestamps, schema_version, and optional hashes/bytes/rows.
"""

from __future__ import annotations
import json, os, tempfile, datetime
from typing import Any, Dict, Optional

LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo  # America/Los_Angeles via OS
DEFAULT_LEVEL = "INFO"

def _now_ts() -> tuple[str, str]:
    now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    return now_utc.isoformat().replace("+00:00", "Z"), now_local.isoformat()

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    _ensure_dir(os.path.dirname(path))
    line = json.dumps(record, separators=(",", ":"), sort_keys=False)
    # Append atomically
    dirpath = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", dir=dirpath, delete=False, encoding="utf-8") as tmp:
        tmp.write(line + "\n")
        tmp_path = tmp.name
    # Atomic rename (best-effort): append by concatenation
    # On Windows, emulate append by open+write; atomicity at file boundary isn’t guaranteed, but acceptable at MVP.
    with open(path, "a", encoding="utf-8") as f:
        with open(tmp_path, "r", encoding="utf-8") as r:
            f.write(r.read())
    os.remove(tmp_path)

def _screen_log_path(session_slug: str, screen: str) -> str:
    """Canonical per-slug JSONL path: artifacts/<slug>/<slug>_screenN_log.jsonl.

    Accepts screen as "S1".."S6" and constructs a slug-prefixed filename
    within the slug folder to align with project conventions.
    """
    screen_norm = screen.lower().lstrip("screen")
    # If caller passed "S1", keep numeric N; else assume already like "s1" or "screen1".
    n = screen[-1]
    fname = f"{session_slug}_screen{n}_log.jsonl"
    return os.path.join("artifacts", session_slug, fname)

def log_event(
    *,
    session_slug: str,
    screen: str,
    event: str,                # e.g., "write_artifact", "export_pack"
    schema_version: str,
    level: str = DEFAULT_LEVEL,
    artifact: Optional[str] = None,
    dataset_hash: Optional[str] = None,
    roles_signature: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    ts_utc, ts_local = _now_ts()
    record = {
        "ts_utc": ts_utc,
        "ts_local": ts_local,
        "screen": screen,
        "event": event,
        "level": level,
        "artifact": artifact,
        "session_slug": session_slug,
        "schema_version": schema_version,
    }
    if dataset_hash:
        record["dataset_hash"] = dataset_hash
    if roles_signature:
        record["roles_signature"] = roles_signature
    if details:
        record["details"] = details
    _append_jsonl(_screen_log_path(session_slug, screen), record)
