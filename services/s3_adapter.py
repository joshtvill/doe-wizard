"""S3 adapter: role assignment & collapse validation (pure; no I/O)."""
from typing import Iterable, Dict, Tuple, List

def candidate_role_columns(df_columns: Iterable[str]) -> list[str]:
    return [c for c in df_columns if c.lower() not in {"y","target","response"}]

def validate_roles(roles: Dict) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not roles.get("responses"):
        errs.append("At least one response must be selected.")
    # Collapse execution required only when grouping keys present (Phase 1 stub)
    return (len(errs) == 0, errs)
