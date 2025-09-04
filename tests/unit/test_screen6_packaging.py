"""
tests/unit/test_screen6_packaging.py

Covers:
 - discovery missing/ present
 - summary derivation (records, features, r2_cv, proposals count)
 - fingerprints presence
 - bundle status success/partial and exceptions[]
 - writes bundle + log
"""

from pathlib import Path
import json

import pytest

from services.handoff_packaging import (
    discover_artifacts, summarize, compute_fingerprints,
    build_bundle, write_outputs
)

def _write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def _csv(p: Path, header, rows):
    _write(p, ",".join(header) + "\n" + "\n".join([",".join(map(str, r)) for r in rows]))

@pytest.fixture
def tmp_artifacts(tmp_path: Path):
    return tmp_path / "artifacts"

def test_packaging_success(tmp_artifacts: Path):
    slug = "250902_demo"
    # minimal required set
    _write(tmp_artifacts / f"{slug}_session_setup.json", "{}")
    _write(tmp_artifacts / f"{slug}_merged_profile.json", "{}")
    _csv(tmp_artifacts / f"{slug}_modeling_ready.csv", ["a","b"], [[1,2],[3,4],[5,6]])
    _write(tmp_artifacts / f"{slug}_roles.json", "{}")
    _write(tmp_artifacts / f"{slug}_datacard.json", "{}")
    _csv(tmp_artifacts / f"{slug}_model_compare.csv", ["m","r2"], [["RF",0.7]])
    _write(tmp_artifacts / f"{slug}_champion_bundle.json", json.dumps({
        "features": ["x1","x2","x3"],
        "model_meta": {"type": "RF"},
        "metrics": {"r2_cv": 0.72}
    }))
    _write(tmp_artifacts / f"{slug}_optimization_settings.json", "{}")
    _csv(tmp_artifacts / f"{slug}_proposals.csv", ["proposal_id","x1","pred","score"], [["p1",0.1,1.2,0.5],["p2",0.3,1.1,0.4]])
    _write(tmp_artifacts / f"{slug}_optimization_trace.json", "{}")
    _write(tmp_artifacts / f"{slug}_screen5_log.json", "{}")

    disc = discover_artifacts(slug, tmp_artifacts)
    assert not disc.missing
    smry = summarize(slug, disc.included)
    assert smry.records == 3
    assert smry.features == 3
    assert smry.champion_model["type"] == "RF"
    assert smry.champion_model["r2_cv"] == 0.72
    assert smry.proposals["count"] == 2
    assert smry.feasibility["ladder"] == "L0"

    fps = compute_fingerprints(disc.included)
    assert fps.data_hash is not None
    assert fps.model_hash is not None
    assert fps.bundle_hash is not None

    bundle = build_bundle(slug, disc, smry, fps, schema_version="2.0", app_version="0.1.0",
                          approvals=[{"name":"A","role":"Owner","timestamp_local":"2025-09-02T12:00:00","decision":"approve","notes":""}])
    assert bundle["status"] == "success"
    assert bundle["exceptions"] == []

    bpath, lpath = write_outputs(slug, tmp_artifacts, bundle)
    assert bpath.exists() and lpath.exists()

    saved = json.loads(bpath.read_text(encoding="utf-8"))
    assert saved["slug"] == slug
    assert saved["summary"]["records"] == 3
    assert saved["summary"]["proposals"]["count"] == 2

def test_packaging_partial_on_missing_proposals(tmp_artifacts: Path):
    slug = "250902_partial"
    # same as above but omit proposals.csv
    _write(tmp_artifacts / f"{slug}_session_setup.json", "{}")
    _write(tmp_artifacts / f"{slug}_merged_profile.json", "{}")
    _csv(tmp_artifacts / f"{slug}_modeling_ready.csv", ["a"], [[1]])
    _write(tmp_artifacts / f"{slug}_roles.json", "{}")
    _write(tmp_artifacts / f"{slug}_datacard.json", "{}")
    _csv(tmp_artifacts / f"{slug}_model_compare.csv", ["m","r2"], [["RF",0.55]])
    _write(tmp_artifacts / f"{slug}_champion_bundle.json", json.dumps({
        "features": ["x1"],
        "model_meta": {"type": "RF"},
        "metrics": {"r2_cv": 0.55}
    }))
    _write(tmp_artifacts / f"{slug}_optimization_settings.json", "{}")
    _write(tmp_artifacts / f"{slug}_optimization_trace.json", "{}")
    _write(tmp_artifacts / f"{slug}_screen5_log.json", "{}")

    disc = discover_artifacts(slug, tmp_artifacts)
    assert any(n.endswith("_proposals.csv") for n in disc.missing)

    smry = summarize(slug, disc.included)
    assert smry.proposals["count"] == 0
    assert smry.feasibility["ladder"] == "L4"

    fps = compute_fingerprints(disc.included)
    bundle = build_bundle(slug, disc, smry, fps)
    assert bundle["status"] == "partial"
    assert any(exc["artifact"].endswith("_proposals.csv") for exc in bundle["exceptions"])
