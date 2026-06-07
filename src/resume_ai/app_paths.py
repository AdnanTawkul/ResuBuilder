from __future__ import annotations

import sys
from pathlib import Path


def _looks_like_project_root(path: Path) -> bool:
    """Return True when a folder looks like the ResuBuilder repository root."""
    return (
        (path / "app.py").exists()
        and (path / "src" / "resume_ai").exists()
    ) or (path / "ResuBuilder.spec").exists()


def project_root() -> Path:
    """Resolve the stable project root for source and PyInstaller runs.

    During development, a PyInstaller build lives under::

        <project>/dist/ResuBuilder/ResuBuilder.exe

    If the app writes data relative to the executable, rebuilt releases wipe the user's
    profiles and workspaces when ``dist/`` is deleted. This resolver walks upward from
    the executable and current working directory to find the repository root first.

    If the app is later distributed outside the repository and no project root marker is
    found, it safely falls back to the executable folder.
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        candidates.append(exe_path.parent)
        candidates.extend(exe_path.parents)
    else:
        candidates.append(Path(__file__).resolve().parents[2])

    candidates.append(Path.cwd().resolve())
    candidates.extend(Path.cwd().resolve().parents)

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if _looks_like_project_root(candidate):
            return candidate

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return project_root() / "data"


def exports_dir() -> Path:
    return project_root() / "exports"


def applications_dir() -> Path:
    return data_dir() / "applications"


def logs_dir() -> Path:
    return data_dir() / "logs"


def profile_path() -> Path:
    return data_dir() / "candidate_profile.json"


def settings_path() -> Path:
    return data_dir() / "settings.json"
