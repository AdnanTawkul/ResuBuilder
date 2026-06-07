from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .app_paths import data_dir, exports_dir, profile_path


DATA_DIR = data_dir()
EXPORT_DIR = exports_dir()
PROFILE_FILE = profile_path()


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(data: dict[str, Any], path: Path = PROFILE_FILE) -> None:
    ensure_directories()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path = PROFILE_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_markdown(filename: str, content: str) -> Path:
    ensure_directories()
    safe_name = filename.strip().replace(" ", "_").lower()
    path = EXPORT_DIR / safe_name
    path.write_text(content, encoding="utf-8")
    return path
