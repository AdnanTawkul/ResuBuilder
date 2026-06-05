TEMPLATES = {
    "ATS Friendly": {
        "description": "Clean structure optimized for applicant tracking systems.",
        "tone": "direct, factual, keyword rich, no graphics",
    },
    "Professional": {
        "description": "Traditional business layout for corporate roles.",
        "tone": "confident, concise, formal",
    },
    "Modern": {
        "description": "Sharper wording for startups, product, design, and tech roles.",
        "tone": "impact focused, modern, concise",
    },
    "Academic CV": {
        "description": "Longer format for research, teaching, grants, and publications.",
        "tone": "detailed, structured, evidence based",
    },
}


def get_template_names() -> list[str]:
    return list(TEMPLATES.keys())


def get_template(template_name: str) -> dict:
    return TEMPLATES.get(template_name, TEMPLATES["ATS Friendly"])
