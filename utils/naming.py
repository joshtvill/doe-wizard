# utils/naming.py
import re
from datetime import datetime

def auto_slug(name: str, date_str: str | None = None) -> str:
    base = re.sub(r"[^a-zA-Z0-9\-]+", "-", (name or "").strip()).strip("-").lower()
    stamp = date_str or datetime.utcnow().strftime("%Y%m%d")
    return f"{base}-{stamp}" if base else stamp
