from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch


@dataclass(frozen=True)
class PDFTemplateConfig:
    name: str
    description: str
    font_regular: str
    font_bold: str
    h1_size: float
    h2_size: float
    body_size: float
    bullet_size: float
    leading_multiplier: float
    title_alignment: int
    left_margin: float
    right_margin: float
    top_margin: float
    bottom_margin: float
    primary_color: colors.Color
    section_line: bool
    section_uppercase: bool
    compact: bool


PDF_TEMPLATES: dict[str, PDFTemplateConfig] = {
    "ATS Friendly": PDFTemplateConfig(
        name="ATS Friendly",
        description="Simple black-and-white layout with conservative spacing. Best for applicant tracking systems.",
        font_regular="Helvetica",
        font_bold="Helvetica-Bold",
        h1_size=18,
        h2_size=11.5,
        body_size=9.4,
        bullet_size=9.2,
        leading_multiplier=1.24,
        title_alignment=TA_CENTER,
        left_margin=0.65 * inch,
        right_margin=0.65 * inch,
        top_margin=0.55 * inch,
        bottom_margin=0.55 * inch,
        primary_color=colors.black,
        section_line=True,
        section_uppercase=True,
        compact=True,
    ),
    "Professional": PDFTemplateConfig(
        name="Professional",
        description="Formal business layout with stronger hierarchy and comfortable spacing.",
        font_regular="Times-Roman",
        font_bold="Times-Bold",
        h1_size=20,
        h2_size=12.5,
        body_size=10,
        bullet_size=9.7,
        leading_multiplier=1.28,
        title_alignment=TA_CENTER,
        left_margin=0.72 * inch,
        right_margin=0.72 * inch,
        top_margin=0.62 * inch,
        bottom_margin=0.62 * inch,
        primary_color=colors.black,
        section_line=True,
        section_uppercase=False,
        compact=False,
    ),
    "Modern": PDFTemplateConfig(
        name="Modern",
        description="Sharper layout with a subtle accent color. Good for tech, product, and startup roles.",
        font_regular="Helvetica",
        font_bold="Helvetica-Bold",
        h1_size=21,
        h2_size=12,
        body_size=9.5,
        bullet_size=9.3,
        leading_multiplier=1.25,
        title_alignment=TA_LEFT,
        left_margin=0.68 * inch,
        right_margin=0.68 * inch,
        top_margin=0.58 * inch,
        bottom_margin=0.58 * inch,
        primary_color=colors.HexColor("#1F4E79"),
        section_line=True,
        section_uppercase=True,
        compact=True,
    ),
    "Academic CV": PDFTemplateConfig(
        name="Academic CV",
        description="Readable long-form layout for education, research, publications, teaching, and grants.",
        font_regular="Times-Roman",
        font_bold="Times-Bold",
        h1_size=19,
        h2_size=12.5,
        body_size=10,
        bullet_size=9.8,
        leading_multiplier=1.3,
        title_alignment=TA_CENTER,
        left_margin=0.78 * inch,
        right_margin=0.78 * inch,
        top_margin=0.68 * inch,
        bottom_margin=0.68 * inch,
        primary_color=colors.black,
        section_line=True,
        section_uppercase=False,
        compact=False,
    ),
}


def get_pdf_template_names() -> list[str]:
    return list(PDF_TEMPLATES.keys())


def get_pdf_template_config(template_name: str) -> PDFTemplateConfig:
    return PDF_TEMPLATES.get(template_name, PDF_TEMPLATES["ATS Friendly"])
