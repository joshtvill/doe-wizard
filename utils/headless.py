# utils/headless.py
from __future__ import annotations
import csv, json, os
from pathlib import Path
from datetime import datetime

ART = Path("artifacts")

def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _write_csv(p: Path, header: list[str], rows: list[list]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def _append_log(slug: str, level: str, msg: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    lp = ART / f"{slug}_screen5_log.json"
    with lp.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_utc": _now(), "level": level, "message": msg}) + "\n")

def ensure_s5_min_artifacts(slug: str) -> None:
    """
    Idempotent: creates minimal S5 outputs if missing.
    Does nothing if files already exist. Safe for CI/headless tests.
    """
    ART.mkdir(parents=True, exist_ok=True)
    settings = ART / f"{slug}_optimization_settings.json"
    proposals = ART / f"{slug}_proposals.csv"
    trace = ART / f"{slug}_optimization_trace.json"

    created = False
    if not settings.exists():
        _write_json(settings, {
            "slug": slug, "created_utc": _now(),
            "bounds": {"x1": [0.0, 1.0]},
            "strategy": {"acq": "ei", "batch_size": 2},
            "constraints": [], "notes": "Headless autorun defaults"
        })
        created = True
    if not proposals.exists():
        _write_csv(proposals, ["proposal_id", "x1", "score"], [["p1", 0.42, 0.8]])
        created = True
    if not trace.exists():
        _write_json(trace, {
            "slug": slug,
            "events": [{"t": _now(), "event": "proposals_generated", "count": 1}]
        })
        created = True
    if created:
        _append_log(slug, "INFO", "ensure_s5_min_artifacts wrote missing S5 artifacts")
