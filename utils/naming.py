# utils/naming.py
import re
from datetime import datetime
from typing import Optional

_slug_re = re.compile(r"[^a-zA-Z0-9\-]+")

def _slugify(text: Optional[str]) -> str:
    """Lowercase, replace non-alnum with '-', collapse/trim dashes."""
    text = (text or "").strip().lower()
    text = _slug_re.sub("-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text

def make_session_slug(
    session_title: str,
    context_tag: str,
    objective: str,
    response: str,
    date_str: Optional[str] = None,
) -> str:
    """
    Contract:
      <YYMMDD>_<Session Title>-<Context Tag>-<Objective>-<Response>
    All components slugified (kebab). Missing pieces are omitted cleanly.
    """
    stamp = date_str or datetime.utcnow().strftime("%y%m%d")  # YYMMDD
    parts = [
        _slugify(session_title),
        _slugify(context_tag),
        _slugify(objective),
        _slugify(response),
    ]
    # Drop empties, join with '-'
    tail = "-".join([p for p in parts if p])
    return f"{stamp}_{tail}" if tail else stamp

# Back-compat (used by early Phase-1 stubs/tests). Prefer make_session_slug going forward.
def auto_slug(name: str, date_str: Optional[str] = None) -> str:
    """Deprecated: kept for compatibility. Produces <YYMMDD>_<name>."""
    return make_session_slug(name, "", "", "", date_str=date_str)
