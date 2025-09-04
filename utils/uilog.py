# utils/uilog.py
"""
UI/logging helpers for append-only JSONL event logs.

Primary API (used by screens):
    write_event_jsonl(path: str, event: dict) -> None

Design:
- Append one JSON object per line (JSONL).
- Create parent directories as needed.
- Be resilient to transient Windows file-lock behavior (retry loop).
- Never raise on logging failures in production paths.
"""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Don't raise from logging helpers
        pass


def write_event_jsonl(path: str, event: Dict[str, Any]) -> None:
    """
    Append a single JSON object as one line to a .json or .jsonl file.

    Args:
        path: Target file path (str). Parent dirs will be created if missing.
        event: Dict payload. Must be JSON-serializable.

    Guarantees:
        - Writes exactly one line per call (trailing '\n').
        - Tolerates transient PermissionError on Windows via short retries.
        - Never raises exceptions to the caller (best-effort logging).
    """
    try:
        p = Path(path)
        _ensure_parent(p)
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        # Short retry loop for Windows file locks
        for _ in range(3):
            try:
                with io.open(p, "a", encoding="utf-8", newline="\n") as f:
                    f.write(payload + "\n")
                return
            except PermissionError:
                time.sleep(0.05)
        # Final attempt (don’t fail the caller even if it still errors)
        with io.open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(payload + "\n")
    except Exception:
        # Swallow all exceptions in logging; never block the main flow
        return


# --- Optional helpers (not currently required by tests) ----------------------

def read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    """
    Safe iterator over JSONL file. Yields dicts; skips malformed lines.
    Never raises if the file is missing.
    """
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except FileNotFoundError:
        return
    except Exception:
        return


def write_screen_event(slug: str, screen_label: str, event: Dict[str, Any]) -> None:
    """
    Convenience: write to artifacts/{slug}_{screen_label}_log.json
    """
    fname = f"artifacts/{slug}_{screen_label}_log.json"
    write_event_jsonl(fname, event)
