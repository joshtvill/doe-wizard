# utils/screenlog.py
"""
Screen-scoped JSONL logging.
- One append-only .jsonl file per screen: artifacts/{slug}_{screen}_log.jsonl
- Delegates to utils.uilog.write_event_jsonl, but guarantees mkdir + append via fallback.
"""

from __future__ import annotations
from typing import Any, Dict
from pathlib import Path
import json
import os

try:
    from utils.uilog import write_event_jsonl as _ui_writer  # type: ignore
except Exception:
    _ui_writer = None  # fallback to local appender below

ARTIFACTS_DIR = Path("artifacts")


def _normalize_screen(screen: str) -> str:
    s = (screen or "").strip().lower()
    if s.startswith("screen"):
        return s
    if s.startswith("s") and s[1:].isdigit():
        return f"screen{s[1:]}"
    return f"screen{s}" if s else "screen1"


def _json_sanitize(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def _local_append_jsonl(payload: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def screen_log(slug: str, screen: str, event: Dict[str, Any]) -> str:
    """
    Append one JSON object (one line) to artifacts/{slug}_{screen}_log.jsonl.
    Returns the absolute path string regardless of writer return value.
    """
    normalized = _normalize_screen(screen)
    # Per-slug folder layout: artifacts/<slug>/<slug>_<screen>_log.jsonl
    path = ARTIFACTS_DIR / slug / f"{slug}_{normalized}_log.jsonl"

    # Build a safe payload and guarantee the directory exists
    payload = {k: _json_sanitize(v) for k, v in (event or {}).items()}
    payload.setdefault("screen", normalized)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer utils.uilog.write_event_jsonl, but guard against signature/behavior differences
    try:
        if _ui_writer is not None:
            # Correct order for utils.uilog.write_event_jsonl is (path, event)
            # Use keywords to be resilient to accidental positional misuse.
            _ui_writer(path=str(path), event=payload)  # type: ignore[call-arg]
        else:
            _local_append_jsonl(payload, path)
    except Exception:
        # Defensive fallback if the UI writer misbehaves
        _local_append_jsonl(payload, path)

    # Best-effort assurance: if nothing wrote (e.g., swallowed error), append locally.
    try:
        if not path.exists() or path.stat().st_size == 0:
            _local_append_jsonl(payload, path)
    except Exception:
        # Never raise from logging path
        pass

    return str(path.resolve())
