# services/artifacts.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ARTIFACTS_DIR = Path("artifacts")

def ensure_dir(p: Path | str) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p

def write_json(obj: Any, path: Path | str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    return path

def read_json(path: Path | str) -> Any:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def list_session_files(suffix: str = "_session_setup.json") -> list[Path]:
    ensure_dir(ARTIFACTS_DIR)
    return sorted(ARTIFACTS_DIR.glob(f"*{suffix}"))
