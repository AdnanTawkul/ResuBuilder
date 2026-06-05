from __future__ import annotations

import os
from typing import Optional

from .models import AISettings, GenerationRequest
from .templates import get_template


class AIService:
    """Generates tailored career documents.

    The app can run without an API key by using a deterministic local draft.
    When an API key is available, it uses OpenAI through the Responses API.
    """

    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"

    def __init__(self) -> None:
        self.environment_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    def has_environment_api_key(self) -> bool:
        return bool(self.environment_api_key)

    def get_default_settings(self) -> AISettings:
        return AISettings(
            use_ai=True,
            api_key=self.environment_api_key,
            model=self.DEFAULT_MODEL,
            generation_mode="Balanced",
        )

    def generate(self, request: GenerationRequest) -> str:
        settings = request.ai_settings
        api_key = self._resolve_api_key(settings)

        if settings.use_ai and api_key:
            ai_result = self._generate_with_openai(request, api_key)
            if ai_result:
                return ai_result

        return self._generate_local_draft(request)

    def test_connection(self, settings: AISettings) -> str:
        api_key = self._resolve_api_key(settings)
        if not api_key:
            return "No API key found. Add a session key or set OPENAI_API_KEY."

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=30.0)
            response = client.responses.create(
                model=settings.model.strip() or self.DEFAULT_MODEL,
                instructions="Reply with exactly: READY",
                input="Connection test.",
                max_output_tokens=20,
            )
            text = (response.output_text or "").strip()
            if text:
                return f"AI connection works. Model response: {text}"
            return "AI connection returned no text. Try a different model name."
        except Exception as exc:
            return f"AI connection failed: {exc}"

    def build_prompt_preview(self, request: GenerationRequest) -> str:
        instructions, user_input = self._build_openai_prompt(request)
        return f"SYSTEM / INSTRUCTIONS\n\n{instructions}\n\nUSER INPUT\n\n{user_input}"

    def _resolve_api_key(self, settings: AISettings) -> str:
        return (settings.api_key or self.environment_api_key or "").strip()

    def _generate_with_openai(self, request: GenerationRequest, api_key: str) -> Optional[str]:
        try:
            from openai import OpenAI

            settings = request.ai_settings
            instructions, user_input = self._build_openai_prompt(request)
            client = OpenAI(api_key=api_key, timeout=90.0)

            response = client.responses.create(
                model=settings.model.strip() or self.DEFAULT_MODEL,
                instructions=instructions,
                input=user_input,
                max_output_tokens=5000,
            )
            text = (response.output_text or "").strip()
            if not text:
                return "AI returned an empty document. Try a different model or add more candidate details."
            return text
        except Exception as exc:
            fallback = self._generate_local_draft(request)
            return (
                "AI generation failed, so a local draft was created instead.\n\n"
                f"Error: {exc}\n\n"
                "---\n\n"
                f"{fallback}"
            )

    def _build_openai_prompt(self, request: GenerationRequest) -> tuple[str, str]:
        profile = request.profile
        template = get_template(request.template_name)
        mode = request.ai_settings.generation_mode.strip() or "Balanced"
        source_document = profile.general_cv if request.document_type.lower() == "cv" else profile.general_resume
        alternate_source = profile.general_resume if request.document_type.lower() == "cv" else profile.general_cv

        instructions = f"""
You are an expert career document strategist and resume writer.
Create a tailored {request.document_type} for the target job.
Output clean Markdown only. Do not wrap the answer in code fences.

Hard rules:
1. Never invent employers, degrees, dates, certifications, tools, metrics, titles, publications, grants, or achievements.
2. If the candidate input lacks a metric, write a strong but truthful bullet without fake numbers.
3. Prioritize evidence that matches the job description.
4. Mirror relevant job-description language only when it is truthful for the candidate.
5. Remove weak, irrelevant, repetitive, or outdated information.
6. Do not include commentary, analysis, warnings, or tailoring notes in the final document.
7. Keep formatting ATS-safe. Use Markdown headings and bullet lists.
8. Make the first third of the document the strongest part.

Template style: {request.template_name}
Template purpose: {template['description']}
Tone: {template['tone']}
Generation mode: {mode}

Mode guidance:
- Conservative: preserve the candidate's original wording more closely and make minimal claims.
- Balanced: improve clarity, ordering, impact, and keyword alignment without overreaching.
- Aggressive: make the positioning sharper and more competitive, but still do not invent facts.

Document rules:
- Resume: target 1 to 2 pages worth of Markdown content. Be concise.
- CV: can be longer and more complete. Include education, projects, research, publications, teaching, and languages when supplied.
- Use the candidate's real contact details at the top.
- Avoid empty sections. If no evidence exists for a section, omit it.
""".strip()

        user_input = f"""
TARGET DOCUMENT TYPE:
{request.document_type}

CANDIDATE DETAILS:
Name: {profile.name}
Email: {profile.email}
Phone: {profile.phone}
Location: {profile.location}
Current or target title: {profile.title}
Links: {profile.links}

Professional summary:
{profile.summary}

Studies / education:
{profile.studies}

Professions / work experience:
{profile.professions}

Projects:
{profile.projects}

Skills:
{profile.skills}

Languages:
{profile.languages}

PRIMARY EXISTING SOURCE DOCUMENT:
{source_document}

SECONDARY EXISTING SOURCE DOCUMENT:
{alternate_source}

TARGET JOB DESCRIPTION:
{request.job_description}
""".strip()
        return instructions, user_input

    def _generate_local_draft(self, request: GenerationRequest) -> str:
        profile = request.profile
        template = get_template(request.template_name)
        keywords = self._extract_keywords(request.job_description)

        heading = "Tailored CV" if request.document_type.lower() == "cv" else "Tailored Resume"
        lines = [
            f"# {heading}",
            "",
            f"## {profile.name or 'Your Name'}",
            f"**{profile.title or 'Target Title'}**",
            "",
            f"Email: {profile.email} | Phone: {profile.phone} | Location: {profile.location}",
            f"Links: {profile.links}",
            "",
            "## Target Role Alignment",
            f"Template: {request.template_name}. {template['description']}",
            f"Relevant keywords detected: {', '.join(keywords) if keywords else 'Add a stronger job description to improve tailoring.'}",
            "",
            "## Professional Summary",
            self._summary(profile, keywords),
            "",
            "## Core Skills",
            self._bullets(profile.skills, fallback="Add your strongest technical, business, and soft skills here."),
            "",
            "## Professional Experience",
            self._bullets(profile.professions, fallback="Add your jobs, responsibilities, dates, and measurable achievements here."),
            "",
            "## Projects",
            self._bullets(profile.projects, fallback="Add projects that prove the skills required in the job description."),
            "",
            "## Education",
            self._bullets(profile.studies, fallback="Add degrees, schools, dates, thesis, honors, and relevant courses."),
            "",
            "## Languages",
            self._bullets(profile.languages, fallback="Add languages and proficiency levels."),
            "",
            "## Tailoring Notes",
            "- OpenAI was not used for this draft. Add an API key in the AI Settings tab for stronger tailoring.",
            "- Replace weak task descriptions with outcomes, tools, and business impact.",
            "- Mirror only truthful job-description keywords.",
            "- Remove irrelevant details that dilute the target position.",
        ]
        return "\n".join(lines).strip()

    def _summary(self, profile, keywords: list[str]) -> str:
        base = profile.summary.strip() or f"{profile.title or 'Professional'} with experience aligned to the target role."
        if keywords:
            return f"{base} Focus areas for this application include {', '.join(keywords[:8])}."
        return base

    def _bullets(self, text: str, fallback: str) -> str:
        items = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
        if not items:
            return f"- {fallback}"
        return "\n".join(f"- {item}" for item in items)

    def _extract_keywords(self, job_description: str) -> list[str]:
        important_terms = []
        candidates = [
            "python", "sql", "excel", "machine learning", "data analysis", "project management",
            "leadership", "communication", "cloud", "aws", "azure", "docker", "git", "api",
            "customer", "sales", "marketing", "research", "finance", "automation", "ai",
            "quality", "testing", "agile", "scrum", "stakeholder", "reporting",
        ]
        lower_text = job_description.lower()
        for term in candidates:
            if term in lower_text:
                important_terms.append(term)
        return important_terms[:12]
