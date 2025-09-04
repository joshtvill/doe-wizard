
from pathlib import Path
from services.artifacts import safe_path, save_json, save_csv
import pandas as pd

def test_safe_path_under_artifacts(tmp_path):
    # simulate repo root
    p = safe_path("foo.json", root=tmp_path)
    # OS-agnostic assertion
    assert p == (tmp_path / "artifacts" / "foo.json")
    assert p.parent.exists()

def test_save_json_and_csv(tmp_path):
    df = pd.DataFrame({"a":[1,2]})
    jp = save_json({"ok": True}, "test.json", root=tmp_path)
    cp = save_csv(df, "test.csv", root=tmp_path)
    assert jp.exists() and cp.exists()
    # extra OS-agnostic checks
    assert jp.parent == (tmp_path / "artifacts")
    assert cp.parent == (tmp_path / "artifacts")
