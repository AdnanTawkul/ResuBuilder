from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from .pdf_exporter import export_markdown_to_pdf


def _slug(value: str, fallback: str = "application") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_").lower()
    return cleaned or fallback


def _unique_directory(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path

    counter = 2
    while True:
        candidate = base_path.with_name(f"{base_path.name}_{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def _safe_pdf_name(prefix: str, company: str, role: str) -> str:
    suffix = "_".join(part for part in [_slug(company, "company"), _slug(role, "role")] if part)
    return f"{prefix}_{suffix}.pdf"


def export_application_package(
    export_root: Path | str,
    metadata: dict[str, Any],
    cv_markdown: str,
    covering_letter_markdown: str,
    quality_report_markdown: str,
    application_snapshot: dict[str, Any],
    page_size: str = "A4",
    template_name: str = "ATS Friendly",
) -> Path:
    """Export a complete application package folder.

    The package contains the final CV PDF, final covering letter PDF, Markdown source files,
    a quality report, and a JSON summary for traceability.
    """

    if not cv_markdown.strip():
        raise ValueError("CV content is missing.")
    if not covering_letter_markdown.strip():
        raise ValueError("Covering letter content is missing.")

    export_root = Path(export_root)
    export_root.mkdir(parents=True, exist_ok=True)

    company = (metadata.get("target_company") or "company").strip()
    role = (metadata.get("target_role") or "role").strip()
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    package_name = f"{_slug(company, 'company')}_{_slug(role, 'role')}_{date_stamp}"
    package_dir = _unique_directory(export_root / package_name)
    package_dir.mkdir(parents=True, exist_ok=False)

    cv_pdf_path = package_dir / _safe_pdf_name("CV", company, role)
    cover_letter_pdf_path = package_dir / _safe_pdf_name("Covering_Letter", company, role)

    export_markdown_to_pdf(
        cv_markdown,
        cv_pdf_path,
        page_size=page_size,
        template_name=template_name,
    )
    export_markdown_to_pdf(
        covering_letter_markdown,
        cover_letter_pdf_path,
        page_size=page_size,
        template_name=template_name,
    )

    (package_dir / "cv.md").write_text(cv_markdown.strip() + "\n", encoding="utf-8")
    (package_dir / "covering_letter.md").write_text(covering_letter_markdown.strip() + "\n", encoding="utf-8")
    (package_dir / "quality_report.md").write_text((quality_report_markdown or "No quality report exported.").strip() + "\n", encoding="utf-8")

    summary = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "target_company": company,
        "target_role": role,
        "application_name": metadata.get("application_name", ""),
        "created_at": metadata.get("created_at", ""),
        "modified_at": metadata.get("modified_at", ""),
        "files": {
            "cv_pdf": cv_pdf_path.name,
            "covering_letter_pdf": cover_letter_pdf_path.name,
            "cv_markdown": "cv.md",
            "covering_letter_markdown": "covering_letter.md",
            "quality_report": "quality_report.md",
            "workspace_snapshot": "application_summary.json",
        },
        "settings": {
            "page_size": page_size,
            "pdf_template": template_name,
        },
        "workspace_snapshot": application_snapshot,
    }
    (package_dir / "application_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return package_dir
