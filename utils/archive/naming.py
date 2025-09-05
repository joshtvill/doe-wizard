# utils/naming.py
from __future__ import annotations
import re
from datetime import datetime
import pytz

def slugify(value: str) -> str:
    """Slugify a string to lowercase alnum+dash."""
    value = value.lower().strip()
    value = re.sub(r"[ _]+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")

def session_slug(context: str, objective: str, response: str) -> str:
    """Build slug = datetime-context-objective-response (UTC stamp)."""
    dt = datetime.now(pytz.utc).strftime("%Y%m%d-%H%M%S")
    parts = [slugify(context), slugify(objective), slugify(response)]
    return f"{dt}-{'-'.join([p for p in parts if p])}"
