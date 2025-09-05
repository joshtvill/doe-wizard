# services/roles.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Literal

from services.artifacts import write_json  # leverage your existing helper

Role = Literal["id", "time", "feature", "response", "ignore"]

# At least one feature and one response; id/time optional in v1
DEFAULT_REQUIRED: dict[str, tuple[int, int | None]] = {
    "feature": (1, None),
    "response": (1, None),
}

def validate_roles(mapping: Dict[str, Role], required: dict[str, tuple[int, int | None]] = DEFAULT_REQUIRED) -> List[str]:
    """Return list of validation error strings (empty if valid)."""
    counts: Dict[str, int] = {"id": 0, "time": 0, "feature": 0, "response": 0, "ignore": 0}
    for r in mapping.values():
        if r not in counts:
            return ["Unknown role detected."]
        counts[r] += 1

    errors: List[str] = []
    for role, (lo, hi) in required.items():
        if counts[role] < lo:
            errors.append(f"Need at least {lo} column(s) with role '{role}'.")
        if hi is not None and counts[role] > hi:
            errors.append(f"Role '{role}' has too many columns (>{hi}).")
    return errors

def save_roles_json(out_path: Path | str, slug: str, mapping: Dict[str, Role]) -> Path:
    """Persist roles manifest using the repo's JSON writer."""
    payload = {
        "slug": slug,
        "schema_version": 1,
        "roles": mapping,
    }
    return write_json(payload, out_path)
