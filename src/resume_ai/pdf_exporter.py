from __future__ import annotations

from html import escape
from pathlib import Path
import re
from typing import Iterable

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


PAGE_SIZES = {
    "A4": A4,
    "Letter": letter,
}


def export_markdown_to_pdf(content: str, output_path: str | Path, page_size: str = "A4") -> Path:
    """Export the generated Markdown-like CV/resume output to a clean PDF.

    This intentionally supports a small, predictable Markdown subset:
    headings, bold text, paragraphs, and bullet lists. That is enough for
    resumes and CVs, and it avoids fragile HTML-to-PDF dependencies.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    story = _build_story(content, styles)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=PAGE_SIZES.get(page_size, A4),
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Tailored CV or Resume",
        author="Resume AI 2",
    )
    doc.build(story)
    return path


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        "h1": ParagraphStyle(
            "ResumeH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ResumeH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "ResumeH3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=7,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "ResumeBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.6,
            leading=12.2,
            spaceAfter=4,
        ),
        "contact": ParagraphStyle(
            "ResumeContact",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11.5,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "ResumeBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=12,
            leftIndent=0,
            spaceAfter=2,
        ),
    }


def _build_story(content: str, styles: dict[str, ParagraphStyle]) -> list:
    story: list = []
    lines = content.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 4))
            index += 1
            continue

        if _is_bullet(line):
            bullet_lines = []
            while index < len(lines) and _is_bullet(lines[index].strip()):
                bullet_lines.append(_strip_bullet(lines[index].strip()))
                index += 1
            story.append(_make_bullet_list(bullet_lines, styles["bullet"]))
            story.append(Spacer(1, 2))
            continue

        if line.startswith("# "):
            story.append(Paragraph(_inline_markup(line[2:].strip()), styles["h1"]))
        elif line.startswith("## "):
            story.append(Paragraph(_inline_markup(line[3:].strip()), styles["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(_inline_markup(line[4:].strip()), styles["h3"]))
        elif _looks_like_contact_line(line):
            story.append(Paragraph(_inline_markup(line), styles["contact"]))
        else:
            story.append(Paragraph(_inline_markup(line), styles["body"]))

        index += 1

    return story or [Paragraph("No content to export.", styles["body"])]


def _make_bullet_list(items: Iterable[str], bullet_style: ParagraphStyle) -> ListFlowable:
    list_items = [
        ListItem(Paragraph(_inline_markup(item), bullet_style), leftIndent=12)
        for item in items
        if item.strip()
    ]
    return ListFlowable(
        list_items,
        bulletType="bullet",
        start="bulletchar",
        bulletFontName="Helvetica",
        bulletFontSize=7,
        leftIndent=16,
    )


def _is_bullet(line: str) -> bool:
    return line.startswith("- ") or line.startswith("* ") or line.startswith("• ")


def _strip_bullet(line: str) -> str:
    return line[2:].strip()


def _looks_like_contact_line(line: str) -> bool:
    lower = line.lower()
    return "email:" in lower or "phone:" in lower or "location:" in lower or "links:" in lower


def _inline_markup(text: str) -> str:
    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    return safe
