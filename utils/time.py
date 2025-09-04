"""utils.time

Pure time helpers. Side‑effect free; no Streamlit imports.
"""

from __future__ import annotations

from datetime import datetime, timezone


def now_utc_iso() -> str:
    """UTC timestamp in ISO‑8601 without microseconds, with 'Z' suffix."""
    return datetime.utcnow().replace(microsecond=0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
