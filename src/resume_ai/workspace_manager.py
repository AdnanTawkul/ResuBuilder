from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

APPLICATIONS_DIR = Path("data") / "applications"
WORKSPACE_SCHEMA_VERSION = 1


def ensure_applications_dir() -> Path:
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return APPLICATIONS_DIR


def make_safe_slug(value: str, fallback: str = "application") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or fallback


def suggested_application_filename(company: str, role: str) -> str:
    date_part = datetime.now().strftime("%Y%m%d")
    company_part = make_safe_slug(company, "company")
    role_part = make_safe_slug(role, "role")
    return f"{company_part}_{role_part}_{date_part}.json"


def save_application_snapshot(path: str | Path, snapshot: dict[str, Any]) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot["schema_version"] = WORKSPACE_SCHEMA_VERSION
    snapshot["saved_at"] = datetime.now().isoformat(timespec="seconds")
    target.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def load_application_snapshot(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Application workspace file is not a JSON object.")
    return data
