import os
from typing import Optional

from .models import GenerationRequest
from .templates import get_template


class AIService:
    """Generates tailored career documents.

    The app works without an API key by using a deterministic local draft.
    When OPENAI_API_KEY is available and the openai package is installed, it can use AI.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    def generate(self, request: GenerationRequest) -> str:
        if self.api_key:
            ai_result = self._generate_with_openai(request)
            if ai_result:
                return ai_result
        return self._generate_local_draft(request)

    def _generate_with_openai(self, request: GenerationRequest) -> Optional[str]:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            profile = request.profile
            template = get_template(request.template_name)

            prompt = f"""
You are an expert resume and CV writer.
Create a tailored {request.document_type} for the job description.
Use the selected template style: {request.template_name}.
Template guidance: {template['description']}.
Tone: {template['tone']}.

Rules:
1. Do not invent employers, degrees, dates, certifications, or achievements.
2. Prioritize role-relevant skills and evidence.
3. Use strong bullet points with measurable impact where the input supports it.
4. Keep resumes concise. CVs may be longer.
5. Output in clean Markdown.

Candidate profile:
Name: {profile.name}
Email: {profile.email}
Phone: {profile.phone}
Location: {profile.location}
Title: {profile.title}
Summary: {profile.summary}
Studies: {profile.studies}
Professions: {profile.professions}
Projects: {profile.projects}
Skills: {profile.skills}
Languages: {profile.languages}
Links: {profile.links}
General CV: {profile.general_cv}
General resume: {profile.general_resume}

Job description:
{request.job_description}
"""
            response = client.responses.create(
                model=self.model,
                input=prompt,
            )
            return response.output_text.strip()
        except Exception as exc:
            return f"AI generation failed, so a local draft was created instead. Error: {exc}\n\n" + self._generate_local_draft(request)

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
            "- Replace weak task descriptions with outcomes, numbers, tools, and business impact.",
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
