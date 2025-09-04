from state import fingerprint_check
from constants import SCHEMA_VERSION


def test_fingerprint_ok():
    upstream = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    current = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    out = fingerprint_check(upstream, current)
    assert out["ok"] is True
    assert out["reasons"] == []


def test_fingerprint_dataset_mismatch():
    upstream = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    current = {"dataset_hash": "zzz", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    out = fingerprint_check(upstream, current)
    assert out["ok"] is False
    assert any("dataset_hash mismatch" in r for r in out["reasons"])


def test_fingerprint_roles_mismatch():
    upstream = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    current = {"dataset_hash": "aaa", "roles_signature": "ccc", "schema_version": SCHEMA_VERSION}
    out = fingerprint_check(upstream, current)
    assert out["ok"] is False
    assert any("roles_signature mismatch" in r for r in out["reasons"])


def test_fingerprint_schema_mismatch_reason_only():
    upstream = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": SCHEMA_VERSION}
    current = {"dataset_hash": "aaa", "roles_signature": "bbb", "schema_version": "old"}
    out = fingerprint_check(upstream, current)
    assert out["ok"] is False
    assert any("schema_version mismatch" in r for r in out["reasons"])

