from __future__ import annotations

from html import escape
from pathlib import Path
import re
from typing import Iterable

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from .pdf_templates import PDFTemplateConfig, get_pdf_template_config


PAGE_SIZES = {
    "A4": A4,
    "Letter": letter,
}


def export_markdown_to_pdf(
    content: str,
    output_path: str | Path,
    page_size: str = "A4",
    template_name: str = "ATS Friendly",
) -> Path:
    """Export the generated Markdown-like CV/resume output to a styled PDF.

    Supported Markdown subset:
    - #, ##, and ### headings
    - bold text with **bold** or __bold__
    - paragraphs
    - bullet lists beginning with -, *, or •

    The limited subset is deliberate. Resume PDFs need predictable layout more
    than full Markdown support.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    template = get_pdf_template_config(template_name)
    styles = _build_styles(template)
    story = _build_story(content, styles, template)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=PAGE_SIZES.get(page_size, A4),
        rightMargin=template.right_margin,
        leftMargin=template.left_margin,
        topMargin=template.top_margin,
        bottomMargin=template.bottom_margin,
        title="Tailored CV or Resume",
        author="Resume AI 2",
    )
    doc.build(story)
    return path


def _build_styles(template: PDFTemplateConfig) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body_leading = template.body_size * template.leading_multiplier
    bullet_leading = template.bullet_size * template.leading_multiplier
    after_small = 2 if template.compact else 4
    after_medium = 5 if template.compact else 7

    return {
        "h1": ParagraphStyle(
            "ResumeH1",
            parent=base["Heading1"],
            fontName=template.font_bold,
            fontSize=template.h1_size,
            leading=template.h1_size * 1.15,
            alignment=template.title_alignment,
            textColor=template.primary_color,
            spaceAfter=after_medium,
        ),
        "subtitle": ParagraphStyle(
            "ResumeSubtitle",
            parent=base["BodyText"],
            fontName=template.font_bold,
            fontSize=template.body_size + 0.4,
            leading=body_leading,
            alignment=template.title_alignment,
            textColor=template.primary_color,
            spaceAfter=after_small,
        ),
        "contact": ParagraphStyle(
            "ResumeContact",
            parent=base["BodyText"],
            fontName=template.font_regular,
            fontSize=max(template.body_size - 0.4, 8.6),
            leading=body_leading,
            alignment=TA_CENTER if template.title_alignment == TA_CENTER else template.title_alignment,
            spaceAfter=after_small,
        ),
        "h2": ParagraphStyle(
            "ResumeH2",
            parent=base["Heading2"],
            fontName=template.font_bold,
            fontSize=template.h2_size,
            leading=template.h2_size * 1.2,
            textColor=template.primary_color,
            spaceBefore=8 if template.compact else 12,
            spaceAfter=3,
        ),
        "h3": ParagraphStyle(
            "ResumeH3",
            parent=base["Heading3"],
            fontName=template.font_bold,
            fontSize=template.body_size + 0.4,
            leading=body_leading,
            spaceBefore=5 if template.compact else 7,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "ResumeBody",
            parent=base["BodyText"],
            fontName=template.font_regular,
            fontSize=template.body_size,
            leading=body_leading,
            spaceAfter=after_small,
        ),
        "bullet": ParagraphStyle(
            "ResumeBullet",
            parent=base["BodyText"],
            fontName=template.font_regular,
            fontSize=template.bullet_size,
            leading=bullet_leading,
            leftIndent=0,
            spaceAfter=1.5 if template.compact else 2.5,
        ),
    }


def _build_story(
    content: str,
    styles: dict[str, ParagraphStyle],
    template: PDFTemplateConfig,
) -> list:
    story: list = []
    lines = _normalize_content(content).splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 2 if template.compact else 4))
            index += 1
            continue

        if _is_bullet(line):
            bullet_lines = []
            while index < len(lines) and _is_bullet(lines[index].strip()):
                bullet_lines.append(_strip_bullet(lines[index].strip()))
                index += 1
            story.append(_make_bullet_list(bullet_lines, styles["bullet"], template))
            story.append(Spacer(1, 1 if template.compact else 3))
            continue

        if line.startswith("# "):
            heading = _clean_generated_heading(line[2:].strip())
            story.append(Paragraph(_inline_markup(heading), styles["h1"]))
        elif line.startswith("## "):
            heading = line[3:].strip()
            if _looks_like_name_heading(heading, story):
                story.append(Paragraph(_inline_markup(heading), styles["h1"]))
            else:
                section_text = heading.upper() if template.section_uppercase else heading
                story.append(Paragraph(_inline_markup(section_text), styles["h2"]))
                if template.section_line:
                    story.append(
                        HRFlowable(
                            width="100%",
                            thickness=0.6,
                            color=template.primary_color,
                            spaceBefore=0,
                            spaceAfter=4 if template.compact else 6,
                        )
                    )
        elif line.startswith("### "):
            story.append(Paragraph(_inline_markup(line[4:].strip()), styles["h3"]))
        elif _looks_like_title_line(line):
            story.append(Paragraph(_inline_markup(_strip_markdown_bold(line)), styles["subtitle"]))
        elif _looks_like_contact_line(line):
            story.append(Paragraph(_inline_markup(line), styles["contact"]))
        else:
            story.append(Paragraph(_inline_markup(line), styles["body"]))

        index += 1

    return story or [Paragraph("No content to export.", styles["body"])]


def _make_bullet_list(
    items: Iterable[str],
    bullet_style: ParagraphStyle,
    template: PDFTemplateConfig,
) -> ListFlowable:
    list_items = [
        ListItem(Paragraph(_inline_markup(item), bullet_style), leftIndent=10 if template.compact else 12)
        for item in items
        if item.strip()
    ]
    return ListFlowable(
        list_items,
        bulletType="bullet",
        start="bulletchar",
        bulletFontName=template.font_regular,
        bulletFontSize=6.5 if template.compact else 7,
        leftIndent=14 if template.compact else 18,
    )


def _normalize_content(content: str) -> str:
    # ReportLab's built-in fonts are safest with simple ASCII punctuation.
    return (
        content.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2022", "•")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _is_bullet(line: str) -> bool:
    return line.startswith("- ") or line.startswith("* ") or line.startswith("• ")


def _strip_bullet(line: str) -> str:
    if line.startswith("• "):
        return line[2:].strip()
    return line[2:].strip()


def _looks_like_name_heading(heading: str, story: list) -> bool:
    # Local drafts currently output "# Tailored Resume" followed by "## Name".
    # Treat the first level-2 heading after the title as the candidate name.
    if not story:
        return False
    lowered = heading.lower()
    forbidden = {
        "target role alignment",
        "professional summary",
        "core skills",
        "professional experience",
        "projects",
        "education",
        "languages",
        "tailoring notes",
    }
    return len(story) <= 3 and lowered not in forbidden and len(heading.split()) <= 5


def _clean_generated_heading(heading: str) -> str:
    lowered = heading.lower().strip()
    if lowered in {"tailored resume", "tailored cv", "resume", "cv"}:
        return heading
    return heading


def _looks_like_title_line(line: str) -> bool:
    stripped = _strip_markdown_bold(line)
    if not stripped or len(stripped) > 90:
        return False
    lowered = stripped.lower()
    title_words = [
        "engineer",
        "developer",
        "manager",
        "analyst",
        "consultant",
        "designer",
        "specialist",
        "scientist",
        "student",
        "intern",
        "director",
        "assistant",
        "coordinator",
    ]
    return line.startswith("**") and line.endswith("**") and any(word in lowered for word in title_words)


def _strip_markdown_bold(text: str) -> str:
    return re.sub(r"^(\*\*|__)(.*?)(\*\*|__)$", r"\2", text.strip())


def _looks_like_contact_line(line: str) -> bool:
    lower = line.lower()
    contact_markers = ["email:", "phone:", "location:", "links:", "linkedin", "github", "portfolio"]
    return any(marker in lower for marker in contact_markers)


def _inline_markup(text: str) -> str:
    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    return safe
