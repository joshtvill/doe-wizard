# services/session_setup_store.py
"""
Session Setup store: create/update a session_setup payload and persist under artifacts/.
Uses the public writer API (services.artifacts.save_json) to avoid coupling to internal helpers.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime

from services.artifacts import save_json  # stable public API

SCHEMA_VERSION = "1.0"


@dataclass
class SessionSetup:
    slug: str
    objective: str
    response_metric: str
    created_utc: str
    schema_version: str = SCHEMA_VERSION
    # Optional free-form context fields
    context: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def default_slug(prefix: str = "run") -> str:
    """Compact timestamp slug: e.g., run20250903_124500."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}{ts}"


def build_payload(
    slug: str,
    objective: str,
    response_metric: str,
    context: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return SessionSetup(
        slug=slug,
        objective=objective,
        response_metric=response_metric,
        created_utc=_now_utc_iso(),
        context=context or None,
        owner=owner or None,
        tags=tags or None,
    ).to_dict()


def write_payload(payload: Dict[str, Any]) -> str:
    """
    Persist to artifacts/{slug}_session_setup.json via services.artifacts.save_json.
    Returns full path as string.
    """
    slug = payload.get("slug", "session")
    basename = f"{slug}_session_setup.json"
    path = save_json(payload, basename)  # save_json handles artifacts/ placement
    return str(path)
