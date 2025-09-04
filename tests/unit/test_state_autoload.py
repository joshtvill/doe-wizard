import hashlib
import json
from pathlib import Path

import pytest

from state import autoload_latest_artifacts, fingerprint_check
from constants import SCHEMA_VERSION


def _sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_autoload_and_fingerprint_ok(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    slug = "tstate"
    art = tmp_path / "artifacts" / slug
    art.mkdir(parents=True, exist_ok=True)

    # Create merged.csv and compute dataset_hash
    merged = art / "merged.csv"
    merged.write_text("a,b\n1,2\n", encoding="utf-8")
    ds = _sha256_path(merged)

    # datacard with roles_signature
    roles_sig = "abc123rolesig"
    (art / "datacard.json").write_text(
        json.dumps({"roles_signature": roles_sig, "schema_version": SCHEMA_VERSION}, indent=2),
        encoding="utf-8",
    )

    # profile with matching dataset_hash and schema_version
    (art / "profile.json").write_text(
        json.dumps({"dataset_hash": ds, "schema_version": SCHEMA_VERSION}, indent=2),
        encoding="utf-8",
    )

    meta = autoload_latest_artifacts(slug)
    assert meta["upstream"]["dataset_hash"] == ds
    assert meta["upstream"]["roles_signature"] == roles_sig
    chk = fingerprint_check(meta["upstream"], meta["current"])
    assert chk["ok"], f"unexpected mismatch: {chk}"


def test_fingerprint_mismatch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    slug = "tstate2"
    art = tmp_path / "artifacts" / slug
    art.mkdir(parents=True, exist_ok=True)

    # Create merged.csv and compute dataset_hash
    merged = art / "merged.csv"
    merged.write_text("a,b\n1,2\n", encoding="utf-8")
    ds = _sha256_path(merged)

    # profile with mismatched dataset_hash
    (art / "profile.json").write_text(
        json.dumps({"dataset_hash": "not-the-same", "schema_version": SCHEMA_VERSION}, indent=2),
        encoding="utf-8",
    )

    meta = autoload_latest_artifacts(slug)
    assert meta["upstream"]["dataset_hash"] == ds
    chk = fingerprint_check(meta["upstream"], meta["current"])
    assert not chk["ok"]
    assert any("dataset_hash" in r for r in chk["reasons"])  # should mention dataset_hash mismatch

