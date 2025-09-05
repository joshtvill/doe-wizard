"""
services/handoff_core.py
--------------------------------
Core helpers for Screen 6 (handoff) packaging:
- Pure utilities (time stamps, hashing, JSON/CSV reads)
- Dataclasses for Discovery/Summary/Fingerprints
- Behavior for discover/summarize/compute_fingerprints/build_bundle
- Writer for outputs + service-level JSONL logging

Used by services/handoff_packaging.py (thin facade) to keep public API stable.
"""

from __future__ import annotations
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Prefer project constants; fall back to default schema_version
try:
    from utils.constants import SCHEMA_VERSION
except Exception:
    SCHEMA_VERSION = "2025-08-29"

from utils.logging import log_event

# ---------------------------
# Required/Optional patterns
# ---------------------------

REQUIRED = {
    # session/meta
    "session": ["{slug}_session_setup.json"],
    # data prep
    "data": [
        "{slug}_merged_profile.json",
        "{slug}_modeling_ready.csv",
        "{slug}_roles.json",
        "{slug}_datacard.json",
    ],
    # modeling
    "modeling": [
        "{slug}_model_compare.csv",
        "{slug}_champion_bundle.json",
    ],
    # optimization
    "optimization": [
        "{slug}_optimization_settings.json",
        "{slug}_proposals.csv",
        "{slug}_optimization_trace.json",
        "{slug}_screen5_log.json",
    ],
}

OPTIONAL = {
    "logs": [
        "screen1_log.json",
        "screen2_log.json",
        "screen3_log.json",
        "screen4_log.json",
        "screen5_log.json",
        "screen6_log.json",
    ]
}

# ---------------------------
# Basic time & IO utilities
# ---------------------------

def _now_iso_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _now_iso_local() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()

def _local_tz_name() -> str:
    """
    Best-effort local timezone name without external deps.
    Tries tzinfo.key (py3.9+ zoneinfo-backed), falls back to str(tzinfo), else 'local'.
    """
    try:
        tz = datetime.now().astimezone().tzinfo
        name = getattr(tz, "key", None)
        if isinstance(name, str) and name:
            return name
        s = str(tz)
        return s if s else "local"
    except Exception:
        return "local"

def _sha256_file(p: Path) -> Optional[str]:
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _read_json(p: Path) -> Optional[dict]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _csv_count_rows(p: Path) -> Optional[int]:
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return 0
        # assume first row is header
        return max(0, len(rows) - 1)
    except Exception:
        return None

# ---------------------------
# Data containers
# ---------------------------

@dataclass
class Discovery:
    included: Dict[str, List[str]]  # category -> list of paths (str)
    missing: List[str]              # missing file basenames (str)

@dataclass
class Summary:
    records: int
    features: int
    champion_model: Dict[str, Optional[object]]
    proposals: Dict[str, Optional[object]]
    feasibility: Dict[str, str]

@dataclass
class Fingerprints:
    data_hash: Optional[str]
    model_hash: Optional[str]
    bundle_hash: Optional[str]

# ---------------------------
# Core behavior
# ---------------------------

def discover_artifacts(slug: str, artifacts_dir: Path) -> Discovery:
    """Locate required & optional artifacts; record missing required by basename."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    inc: Dict[str, List[str]] = {k: [] for k in ["session", "data", "modeling", "optimization", "logs"]}
    missing: List[str] = []

    def _resolve(fname: str) -> Optional[Path]:
        # Try flat first
        p_flat = artifacts_dir / fname
        if p_flat.exists():
            return p_flat
        # If name is slug-prefixed, map to foldered artifacts/<slug>/<name>
        if fname.startswith(f"{slug}_"):
            name_only = fname[len(slug) + 1 :]
            p_folder = artifacts_dir / slug / name_only
            if p_folder.exists():
                return p_folder
        return None

    # required
    for cat, patterns in REQUIRED.items():
        for pat in patterns:
            fname = pat.format(slug=slug)
            rp = _resolve(fname)
            if rp is not None:
                inc[cat].append(str(rp))
            else:
                missing.append(fname)

    # optional logs (best-effort)
    for fname in OPTIONAL["logs"]:
        # OPTIONAL may include either slugless or slugged patterns; accept .json or .jsonl
        candidates = [
            artifacts_dir / fname,
            artifacts_dir / slug / fname,
            artifacts_dir / slug / f"{slug}_{fname}",
        ]
        if fname.endswith(".json"):
            alt = fname[:-5] + ".jsonl"
            candidates += [
                artifacts_dir / alt,
                artifacts_dir / slug / alt,
                artifacts_dir / slug / f"{slug}_{alt}",
            ]
        for candidate in candidates:
            if candidate.exists():
                inc["logs"].append(str(candidate))
                break

    return Discovery(included=inc, missing=missing)


def summarize(slug: str, inc: Dict[str, List[str]]) -> Summary:
    """Derive summary metrics from discovered artifacts (tolerant of missing)."""
    # records from modeling_ready.csv
    modeling_ready = _first_match(inc["data"], suffix="_modeling_ready.csv")
    records = _csv_count_rows(Path(modeling_ready)) if modeling_ready else 0

    # features & champion model stats
    champion_path = _first_match(inc["modeling"], suffix="_champion_bundle.json")
    features = 0
    model_type = None
    r2_cv = None
    if champion_path:
        champ = _read_json(Path(champion_path)) or {}
        feats = champ.get("features") or champ.get("feature_names") or []
        features = len(feats) if isinstance(feats, list) else 0
        meta = champ.get("model_meta") or champ.get("model") or {}
        model_type = meta.get("type") or meta.get("model_type")
        metrics = champ.get("metrics") or {}
        r2_cv = metrics.get("r2_cv") or metrics.get("r2") or None

    # proposals count
    proposals_csv = _first_match(inc["optimization"], suffix="_proposals.csv")
    proposals_count = _csv_count_rows(Path(proposals_csv)) if proposals_csv else 0

    # feasibility ladder heuristic (MVP)
    ladder = "L0" if (proposals_count and proposals_count > 0) else "L4"

    return Summary(
        records=int(records or 0),
        features=int(features or 0),
        champion_model={"type": model_type, "r2_cv": r2_cv, "notes": ""},
        proposals={"count": int(proposals_count or 0), "batch_size": None},
        feasibility={"ladder": ladder, "notes": ""},
    )


def compute_fingerprints(inc: Dict[str, List[str]]) -> Fingerprints:
    """Compute SHA256 for key items and an aggregate bundle hash."""
    # choose canonical files for data & model
    data_path = _find_first(inc, "_modeling_ready.csv")
    model_path = _find_first(inc, "_champion_bundle.json")

    data_hash = _sha256_file(Path(data_path)) if data_path else None
    model_hash = _sha256_file(Path(model_path)) if model_path else None

    # aggregate hash across *all* included files (sorted names)
    all_files = sorted({p for lst in inc.values() for p in lst})
    h = hashlib.sha256()
    for p in all_files:
        ph = _sha256_file(Path(p))
        if ph:
            h.update(ph.encode("utf-8"))
    bundle_hash = h.hexdigest() if all_files else None

    return Fingerprints(data_hash=data_hash, model_hash=model_hash, bundle_hash=bundle_hash)


def build_bundle(
    slug: str,
    discovery: Discovery,
    summary: Summary,
    fingerprints: Fingerprints,
    schema_version: str = SCHEMA_VERSION,
    app_version: str = "0.1.0",
    local_tz_name: Optional[str] = None,
    approvals: Optional[List[Dict[str, str]]] = None,
) -> Dict:
    """Assemble the full handoff bundle JSON."""
    local_tz_name = local_tz_name or _local_tz_name()
    status = "success" if len(discovery.missing) == 0 else "partial"

    bundle = {
        "slug": slug,
        "created_utc": _now_iso_utc(),
        "local_tz": local_tz_name,
        "status": status,
        "artifacts_included": discovery.included,
        "summary": {
            "records": summary.records,
            "features": summary.features,
            "champion_model": summary.champion_model,
            "proposals": summary.proposals,
            "feasibility": summary.feasibility,
        },
        "exceptions": [
            {"artifact": m, "reason": "missing", "notes": ""} for m in discovery.missing
        ],
        "approvals": approvals or [],
        "fingerprints": {
            "data_hash": fingerprints.data_hash,
            "model_hash": fingerprints.model_hash,
            "bundle_hash": fingerprints.bundle_hash,
        },
        "versions": {
            "schema_version": schema_version,
            "app_version": app_version,
        },
    }
    return bundle


def write_outputs(slug: str, artifacts_dir: Path, bundle: Dict, hitl_notes: Optional[str] = None) -> Tuple[Path, Path]:
    """
    Write <slug>_handoff_bundle.json and append to <slug>_handoff_log.json; also log to screen6_log.jsonl.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = artifacts_dir / f"{slug}_handoff_bundle.json"
    log_path = artifacts_dir / f"{slug}_handoff_log.json"

    # write bundle (overwrite ok)
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    # append legacy handoff log entry (JSON Lines)
    entry = {
        "ts_utc": _now_iso_utc(),
        "ts_local": _now_iso_local(),
        "action": "export_handoff",
        "slug": slug,
        "status": bundle.get("status", ""),
        "exceptions_count": len(bundle.get("exceptions", [])),
        "notes": hitl_notes or "",
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # NEW: service-level JSONL event in screen6_log.jsonl
    try:
        size = bundle_path.stat().st_size
        log_event(
            session_slug=slug,
            screen="S6",
            event="handoff_bundle",
            artifact=f"{slug}_handoff_bundle.json",
            schema_version=bundle.get("versions", {}).get("schema_version", SCHEMA_VERSION),
            details={"bytes": size, "exceptions_count": entry["exceptions_count"]},
        )
    except Exception:
        # Logging must not break packaging; swallow but keep legacy log.
        pass

    return bundle_path, log_path

# ---------------------------
# Internal find helpers
# ---------------------------

def _first_match(paths: List[str], suffix: str) -> Optional[str]:
    for p in paths:
        if p.endswith(suffix):
            return p
    return None

def _find_first(inc: Dict[str, List[str]], suffix: str) -> Optional[str]:
    for lst in inc.values():
        for p in lst:
            if p.endswith(suffix):
                return p
    return None
