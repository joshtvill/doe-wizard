from __future__ import annotations
from pathlib import Path
from typing import Optional

ART = Path("artifacts")


def resolve(slug: str, name: str) -> Path:
    """Return the preferred path for an artifact, tolerant of flat or foldered layout.

    Order of preference when existing:
    - artifacts/<slug>_<name>
    - artifacts/<slug>/<name>

    If neither exists, returns the flat-form path for callers to create.
    """
    flat = ART / f"{slug}_{name}"
    folder = ART / slug / name
    folder_slugged = ART / slug / f"{slug}_{name}"
    # Prefer new per-slug layout first
    if folder_slugged.exists():
        return folder_slugged
    if folder.exists():
        return folder
    if flat.exists():
        return flat
    # default to foldered slug+name path for new writes
    return folder_slugged


def ensure_text(slug: str, name: str, text: str) -> Path:
    """Write text to the artifact path, choosing flat form unless a folder for slug already exists."""
    ART.mkdir(exist_ok=True)
    folder_dir = ART / slug
    p = folder_dir / name if folder_dir.exists() else ART / f"{slug}_{name}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p
