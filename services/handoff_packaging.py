"""
services/handoff_packaging.py
=============================
Thin facade that exposes the same public API for S6 handoff while delegating
to services/handoff_core.py for the behavior.

Public API preserved:
- Discovery, Summary, Fingerprints dataclasses
- discover_artifacts
- summarize
- compute_fingerprints
- build_bundle
- write_outputs
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Re-export dataclasses and functions from the core
from .handoff_core import (
    Discovery,
    Summary,
    Fingerprints,
    discover_artifacts,
    summarize,
    compute_fingerprints,
    build_bundle,
    write_outputs,
)

__all__ = [
    "Discovery",
    "Summary",
    "Fingerprints",
    "discover_artifacts",
    "summarize",
    "compute_fingerprints",
    "build_bundle",
    "write_outputs",
]
