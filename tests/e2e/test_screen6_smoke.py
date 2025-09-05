"""
tests/e2e/test_screen6_smoke.py

Happy path & partial path exercised end-to-end using the packaging service.
"""

from pathlib import Path
import json
from services.handoff_packaging import (
    discover_artifacts, summarize, compute_fingerprints, build_bundle, write_outputs
)

def _write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def _csv(p: Path, header, rows):
    _write(p, ",".join(header) + "\n" + "\n".join([",".join(map(str, r)) for r in rows]))

def test_e2e_happy(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    slug = "250902_e2e"
    # create a minimally complete set
    _write(artifacts / f"{slug}_session_setup.json", "{}")
    _write(artifacts / f"{slug}_merged_profile.json", "{}")
    _csv(artifacts / f"{slug}_modeling_ready.csv", ["f1","f2"], [[1,2],[3,4]])
    _write(artifacts / f"{slug}_roles.json", "{}")
    _write(artifacts / f"{slug}_datacard.json", "{}")
    _csv(artifacts / f"{slug}_model_compare.csv", ["m","r2"], [["GPR",0.8]])
    _write(artifacts / f"{slug}_champion_bundle.json", json.dumps({
        "features": ["f1","f2","f3"],
        "model_meta": {"type": "GPR"},
        "metrics": {"r2_cv": 0.80}
    }))
    _write(artifacts / f"{slug}_optimization_settings.json", "{}")
    _csv(artifacts / f"{slug}_proposals.csv", ["proposal_id","f1","score"], [["p1",0.1,0.9]])
    _write(artifacts / f"{slug}_optimization_trace.json", "{}")
    _write(artifacts / f"{slug}_screen5_log.json", "{}")

    disc = discover_artifacts(slug, artifacts)
    smry = summarize(slug, disc.included)
    fps  = compute_fingerprints(disc.included)
    bundle = build_bundle(slug, disc, smry, fps, approvals=[{"name":"QA","role":"Owner","timestamp_local":"2025-09-02T12:00:00","decision":"approve","notes":""}])
    bpath, lpath = write_outputs(slug, artifacts, bundle)
    assert bpath.exists() and lpath.exists()

def test_e2e_partial(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    slug = "250902_e2e_partial"
    # omit proposals
    _write(artifacts / f"{slug}_session_setup.json", "{}")
    _write(artifacts / f"{slug}_merged_profile.json", "{}")
    _csv(artifacts / f"{slug}_modeling_ready.csv", ["f1"], [[1]])
    _write(artifacts / f"{slug}_roles.json", "{}")
    _write(artifacts / f"{slug}_datacard.json", "{}")
    _csv(artifacts / f"{slug}_model_compare.csv", ["m","r2"], [["XGB",0.5]])
    _write(artifacts / f"{slug}_champion_bundle.json", json.dumps({
        "features": ["f1"],
        "model_meta": {"type": "XGB"},
        "metrics": {"r2_cv": 0.50}
    }))
    _write(artifacts / f"{slug}_optimization_settings.json", "{}")
    _write(artifacts / f"{slug}_optimization_trace.json", "{}")
    _write(artifacts / f"{slug}_screen5_log.json", "{}")

    disc = discover_artifacts(slug, artifacts)
    smry = summarize(slug, disc.included)
    fps  = compute_fingerprints(disc.included)
    bundle = build_bundle(slug, disc, smry, fps)
    assert bundle["status"] == "partial"
    bpath, lpath = write_outputs(slug, artifacts, bundle)
    assert bpath.exists() and lpath.exists()
