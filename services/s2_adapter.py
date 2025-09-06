"""S2 adapter: files/join/profile orchestration shell (pure stubs for Phase 1)."""
from typing import Iterable

def validate_files(features_loaded: bool, response_loaded: bool) -> tuple[bool, list[str]]:
    errs = []
    if not features_loaded: errs.append("Features CSV required.")
    return (len(errs) == 0, errs)

def validate_join_keys(pairs: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    if not pairs: return (True, [])
    errs = []
    for i,(l,r) in enumerate(pairs, start=1):
        if not l or not r: errs.append(f"Join key row {i} incomplete.")
    return (len(errs) == 0, errs)

def profile_preview_columns(cols: Iterable[str]) -> list[str]:
    return list(cols)[:10]
