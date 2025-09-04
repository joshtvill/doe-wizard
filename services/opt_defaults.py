"""
SERVICES :: opt_defaults.py

Default settings and minimal recompute helper for Screen 5.
"""

from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import pandas as pd
from services import artifacts as _art


def get_default_settings() -> Dict[str, Any]:
    return {
        "acquisition": "EI",
        "batch_size": 4,
        "ucb_k": 1.96,
        "uncertainty_mode": "deterministic",
        "seed": 1729,
    }


def recompute_optimization(session_slug: str, settings: Dict[str, Any] | None = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Minimal recompute: write optimization_settings.json, proposals.csv (empty), and optimization_trace.json stub.
    Uses artifacts writer to attach schema_version.
    """
    sdir = Path("artifacts") / session_slug
    sdir.mkdir(parents=True, exist_ok=True)

    opt_settings = settings or get_default_settings()
    settings_path = sdir / "optimization_settings.json"
    _art.save_json(opt_settings, f"{session_slug}_optimization_settings.json")

    proposals_path = sdir / "proposals.csv"
    pd.DataFrame([]).to_csv(proposals_path, index=False)

    trace = {"steps": []}
    trace_path = sdir / "optimization_trace.json"
    _art.save_json(trace, f"{session_slug}_optimization_trace.json")

    return {
        "written": [
            {"artifact": "optimization_settings.json", "path": str(settings_path.resolve())},
            {"artifact": "proposals.csv", "path": str(proposals_path.resolve())},
            {"artifact": "optimization_trace.json", "path": str(trace_path.resolve())},
        ]
    }
