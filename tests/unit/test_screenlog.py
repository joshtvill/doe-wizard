import json
from pathlib import Path


def test_screen_log_writes_jsonl_and_normalizes_screen(monkeypatch, tmp_path):
    # Run in an isolated cwd so artifacts/ goes under tmp_path
    monkeypatch.chdir(tmp_path)
    from utils.screenlog import screen_log

    out = screen_log("smoke_slug", "s1", {"event": "smoke", "n": 1})
    p = Path(out)

    # File exists and is under artifacts/<slug>/
    assert p.exists(), "screen_log should create the jsonl file"
    assert p.name == "smoke_slug_screen1_log.jsonl"
    # Expect per-slug folder layout
    assert p.parent.name == "smoke_slug"
    assert p.parent.parent.name == "artifacts"

    # Last line decodes to JSON and includes normalized screen
    tail = p.read_text(encoding="utf-8").splitlines()[-1]
    obj = json.loads(tail)
    assert obj["event"] == "smoke"
    assert obj["n"] == 1
    assert obj["screen"] == "screen1"


def test_screen_log_fallback_when_ui_writer_noops(monkeypatch, tmp_path):
    # Run in isolated cwd
    monkeypatch.chdir(tmp_path)
    import importlib
    import utils.screenlog as sl

    # Ensure clean module state
    importlib.reload(sl)

    # Patch the UI writer to a no-op (does not write any file)
    def _noop_writer(*, path: str, event: dict):  # matches keyword usage
        return None

    monkeypatch.setattr(sl, "_ui_writer", _noop_writer, raising=False)

    out = sl.screen_log("smoke_slug", "screen2", {"event": "fallthrough"})
    p = Path(out)
    assert p.exists(), "fallback appender should create the file when UI writer does nothing"
    tail = p.read_text(encoding="utf-8").splitlines()[-1]
    obj = json.loads(tail)
    assert obj["event"] == "fallthrough"
    assert obj["screen"] == "screen2"
