from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from .models import AISettings, GenerationRequest
from .templates import get_template


class AIService:
    """Generates tailored career documents using cloud AI, local AI, or fallback drafts."""

    PROVIDER_OPENAI = "OpenAI"
    PROVIDER_OLLAMA = "Ollama Local"

    DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:14b").strip() or "qwen3:14b"
    DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"

    def __init__(self) -> None:
        self.environment_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    def has_environment_api_key(self) -> bool:
        return bool(self.environment_api_key)

    def get_default_settings(self) -> AISettings:
        default_provider = self.PROVIDER_OPENAI if self.environment_api_key else self.PROVIDER_OLLAMA
        return AISettings(
            use_ai=True,
            provider=default_provider,
            api_key=self.environment_api_key,
            model=self.DEFAULT_OPENAI_MODEL,
            generation_mode="Balanced",
            ollama_base_url=self.DEFAULT_OLLAMA_BASE_URL,
            ollama_model=self.DEFAULT_OLLAMA_MODEL,
            timeout_seconds=120,
        )

    def generate(self, request: GenerationRequest) -> str:
        settings = request.ai_settings
        if not settings.use_ai:
            return self._generate_local_draft(request, note="AI is disabled in the AI Settings tab.")

        provider = self._normalize_provider(settings.provider)

        if provider == self.PROVIDER_OLLAMA:
            ai_result = self._generate_with_ollama(request)
            if ai_result:
                return ai_result
            return self._generate_local_draft(request, note="Ollama did not return a usable document.")

        if provider == self.PROVIDER_OPENAI:
            api_key = self._resolve_api_key(settings)
            if api_key:
                ai_result = self._generate_with_openai(request, api_key)
                if ai_result:
                    return ai_result
            return self._generate_local_draft(request, note="No OpenAI API key was available.")

        return self._generate_local_draft(request, note=f"Unknown AI provider: {settings.provider}")

    def test_connection(self, settings: AISettings) -> str:
        provider = self._normalize_provider(settings.provider)
        if provider == self.PROVIDER_OLLAMA:
            return self._test_ollama_connection(settings)
        if provider == self.PROVIDER_OPENAI:
            return self._test_openai_connection(settings)
        return f"AI connection failed: unknown provider '{settings.provider}'."

    def build_prompt_preview(self, request: GenerationRequest) -> str:
        instructions, user_input = self._build_generation_prompt(request)
        provider = self._normalize_provider(request.ai_settings.provider)
        model = self._selected_model_name(request.ai_settings)
        return (
            f"AI PROVIDER\n\n{provider}\n\n"
            f"MODEL\n\n{model}\n\n"
            f"SYSTEM / INSTRUCTIONS\n\n{instructions}\n\n"
            f"USER INPUT\n\n{user_input}"
        )

    def review_document(self, request: GenerationRequest, generated_document: str, heuristic_report: str) -> str:
        settings = request.ai_settings
        if not settings.use_ai:
            return "AI review was skipped because AI is disabled in the AI Settings tab."

        provider = self._normalize_provider(settings.provider)
        instructions, user_input = self._build_review_prompt(request, generated_document, heuristic_report)

        if provider == self.PROVIDER_OLLAMA:
            try:
                response = self._call_ollama_chat(
                    settings=settings,
                    messages=[
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": user_input},
                    ],
                    timeout=float(settings.timeout_seconds or 120),
                    num_predict=1800,
                )
                text = self._extract_ollama_text(response).strip()
                return self._clean_local_model_output(text) if text else "Ollama returned an empty quality review."
            except Exception as exc:
                return f"Ollama quality review failed: {exc}"

        if provider == self.PROVIDER_OPENAI:
            api_key = self._resolve_api_key(settings)
            if not api_key:
                return "OpenAI quality review failed: add a session key or set OPENAI_API_KEY."
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=float(settings.timeout_seconds or 120))
                response = client.responses.create(
                    model=settings.model.strip() or self.DEFAULT_OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    max_output_tokens=2500,
                )
                text = (response.output_text or "").strip()
                return text if text else "OpenAI returned an empty quality review."
            except Exception as exc:
                return f"OpenAI quality review failed: {exc}"

        return f"AI quality review failed: unknown provider '{settings.provider}'."


    def improve_document(
        self,
        request: GenerationRequest,
        generated_document: str,
        heuristic_report: str,
        ai_review: str = "",
    ) -> str:
        """Regenerates the current document using the quality report as constraints."""
        settings = request.ai_settings
        if not settings.use_ai:
            return "AI improvement failed: AI is disabled in the AI Settings tab."

        provider = self._normalize_provider(settings.provider)
        instructions, user_input = self._build_improvement_prompt(
            request=request,
            generated_document=generated_document,
            heuristic_report=heuristic_report,
            ai_review=ai_review,
        )

        if provider == self.PROVIDER_OLLAMA:
            try:
                response = self._call_ollama_chat(
                    settings=settings,
                    messages=[
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": user_input},
                    ],
                    timeout=float(settings.timeout_seconds or 180),
                    num_predict=2800,
                )
                text = self._extract_ollama_text(response).strip()
                if not text:
                    return "Ollama returned an empty improved document. Add more candidate evidence or try again."
                return self._clean_local_model_output(text)
            except Exception as exc:
                return f"Ollama improvement failed: {exc}"

        if provider == self.PROVIDER_OPENAI:
            api_key = self._resolve_api_key(settings)
            if not api_key:
                return "OpenAI improvement failed: add a session key or set OPENAI_API_KEY."
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=float(settings.timeout_seconds or 180))
                response = client.responses.create(
                    model=settings.model.strip() or self.DEFAULT_OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    max_output_tokens=5000,
                )
                text = (response.output_text or "").strip()
                return text if text else "OpenAI returned an empty improved document."
            except Exception as exc:
                return f"OpenAI improvement failed: {exc}"

        return f"AI improvement failed: unknown provider '{settings.provider}'."

    def _normalize_provider(self, provider: str) -> str:
        provider = (provider or "").strip().lower()
        if provider in {"ollama", "ollama local", "local"}:
            return self.PROVIDER_OLLAMA
        if provider in {"openai", "openai responses api"}:
            return self.PROVIDER_OPENAI
        return self.PROVIDER_OLLAMA

    def _selected_model_name(self, settings: AISettings) -> str:
        provider = self._normalize_provider(settings.provider)
        if provider == self.PROVIDER_OLLAMA:
            return settings.ollama_model.strip() or self.DEFAULT_OLLAMA_MODEL
        return settings.model.strip() or self.DEFAULT_OPENAI_MODEL

    def _resolve_api_key(self, settings: AISettings) -> str:
        return (settings.api_key or self.environment_api_key or "").strip()

    def _test_openai_connection(self, settings: AISettings) -> str:
        api_key = self._resolve_api_key(settings)
        if not api_key:
            return "OpenAI connection failed: add a session key or set OPENAI_API_KEY."

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=float(settings.timeout_seconds or 60))
            response = client.responses.create(
                model=settings.model.strip() or self.DEFAULT_OPENAI_MODEL,
                instructions="Reply with exactly: READY",
                input="Connection test.",
                max_output_tokens=20,
            )
            text = (response.output_text or "").strip()
            if text:
                return f"OpenAI connection works. Model response: {text}"
            return "OpenAI connection returned no text. Try a different model name."
        except Exception as exc:
            return f"OpenAI connection failed: {exc}"

    def _test_ollama_connection(self, settings: AISettings) -> str:
        try:
            response = self._call_ollama_chat(
                settings=settings,
                messages=[{"role": "user", "content": "Reply with exactly: READY"}],
                timeout=min(float(settings.timeout_seconds or 60), 60.0),
                num_predict=20,
            )
            text = self._extract_ollama_text(response)
            if text:
                return f"Ollama connection works. Model response: {text[:200]}"
            return "Ollama connection returned no text. Check the model name."
        except Exception as exc:
            return f"Ollama connection failed: {exc}"

    def _generate_with_openai(self, request: GenerationRequest, api_key: str) -> Optional[str]:
        try:
            from openai import OpenAI

            settings = request.ai_settings
            instructions, user_input = self._build_generation_prompt(request)
            client = OpenAI(api_key=api_key, timeout=float(settings.timeout_seconds or 120))

            response = client.responses.create(
                model=settings.model.strip() or self.DEFAULT_OPENAI_MODEL,
                instructions=instructions,
                input=user_input,
                max_output_tokens=5000,
            )
            text = (response.output_text or "").strip()
            if not text:
                return "OpenAI returned an empty document. Try a different model or add more candidate details."
            return text
        except Exception as exc:
            fallback = self._generate_local_draft(request, note="OpenAI generation failed.")
            return (
                "OpenAI generation failed, so a local non-AI draft was created instead.\n\n"
                f"Error: {exc}\n\n"
                "---\n\n"
                f"{fallback}"
            )

    def _generate_with_ollama(self, request: GenerationRequest) -> Optional[str]:
        try:
            settings = request.ai_settings
            instructions, user_input = self._build_generation_prompt(request)
            response = self._call_ollama_chat(
                settings=settings,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user_input},
                ],
                timeout=float(settings.timeout_seconds or 120),
                num_predict=3500,
            )
            text = self._extract_ollama_text(response).strip()
            if not text:
                return "Ollama returned an empty document. Check the model name or add more candidate details."
            return self._clean_local_model_output(text)
        except Exception as exc:
            fallback = self._generate_local_draft(request, note="Ollama generation failed.")
            return (
                "Ollama generation failed, so a local non-AI draft was created instead.\n\n"
                f"Error: {exc}\n\n"
                "---\n\n"
                f"{fallback}"
            )

    def _call_ollama_chat(
        self,
        settings: AISettings,
        messages: list[dict[str, str]],
        timeout: float,
        num_predict: int = 3000,
    ) -> dict:
        base_url = (settings.ollama_base_url or self.DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")
        model = (settings.ollama_model or self.DEFAULT_OLLAMA_MODEL).strip()
        url = f"{base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self._temperature_for_mode(settings.generation_mode),
                "num_predict": int(num_predict),
                "num_ctx": 8192,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from Ollama at {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {base_url}. Make sure Ollama is running and the base URL is correct."
            ) from exc

    def _extract_ollama_text(self, response: dict) -> str:
        message = response.get("message", {}) if isinstance(response, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        return str(content or "").strip()

    def _clean_local_model_output(self, text: str) -> str:
        cleaned = text.strip()
        for marker in ("<think>", "</think>"):
            cleaned = cleaned.replace(marker, "")

        lowered = cleaned.lower().strip()
        if lowered.startswith("```markdown"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        elif lowered.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""

        if cleaned.strip().endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]

        return cleaned.strip()

    def _temperature_for_mode(self, mode: str) -> float:
        normalized = (mode or "Balanced").strip().lower()
        if normalized == "conservative":
            return 0.2
        if normalized == "aggressive":
            return 0.7
        return 0.4

    def _build_generation_prompt(self, request: GenerationRequest) -> tuple[str, str]:
        profile = request.profile
        template = get_template(request.template_name)
        mode = request.ai_settings.generation_mode.strip() or "Balanced"
        source_document = profile.general_cv if request.document_type.lower() == "cv" else profile.general_resume
        alternate_source = profile.general_resume if request.document_type.lower() == "cv" else profile.general_cv

        instructions = f"""
You are an expert career document strategist and resume writer.
Create a tailored {request.document_type} for the target job.
Output clean Markdown only. Do not wrap the answer in code fences.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, analysis notes, or implementation details.

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

    def _build_review_prompt(self, request: GenerationRequest, generated_document: str, heuristic_report: str) -> tuple[str, str]:
        profile = request.profile
        source_document = profile.general_cv if request.document_type.lower() == "cv" else profile.general_resume
        alternate_source = profile.general_resume if request.document_type.lower() == "cv" else profile.general_cv

        instructions = f"""
You are a strict resume and CV quality reviewer.
Review the generated {request.document_type} against the target job and the candidate evidence.
Output clean Markdown only. Do not wrap the answer in code fences.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, or implementation details.

Hard rules:
1. Do not rewrite the full resume or CV. Review it.
2. Identify unsupported claims, fake-looking metrics, placeholders, weak bullets, and keyword gaps.
3. Do not suggest adding a keyword unless it is truthful based on candidate evidence.
4. Separate critical fixes from optional improvements.
5. Be direct and specific.

Required Markdown sections:
# AI Quality Review
## Critical risks
## Missing or weak evidence
## Keyword alignment
## ATS and formatting
## Top 5 fixes before export
""".strip()

        user_input = f"""
TARGET DOCUMENT TYPE:
{request.document_type}

CANDIDATE EVIDENCE:
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

GENERATED DOCUMENT TO REVIEW:
{generated_document}

HEURISTIC QUALITY REPORT:
{heuristic_report}
""".strip()
        return instructions, user_input

    def _build_improvement_prompt(
        self,
        request: GenerationRequest,
        generated_document: str,
        heuristic_report: str,
        ai_review: str = "",
    ) -> tuple[str, str]:
        profile = request.profile
        source_document = profile.general_cv if request.document_type.lower() == "cv" else profile.general_resume
        alternate_source = profile.general_resume if request.document_type.lower() == "cv" else profile.general_cv

        instructions = f"""
You are an expert resume and CV editor.
Rewrite the current {request.document_type} using the quality report as constraints.
Output the improved {request.document_type} only, in clean Markdown.
Do not wrap the answer in code fences.
Do not include analysis, notes, explanations, or quality-review commentary.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, or implementation details.

Hard rules:
1. Never invent employers, clients, projects, degrees, dates, certifications, metrics, tools, titles, or achievements.
2. Do not add consulting, DevOps, ETL, REST, cloud, architecture, or client-facing claims unless the candidate evidence clearly supports them.
3. If the job uses a keyword but the candidate evidence does not support it, omit the keyword instead of faking alignment.
4. Improve keyword alignment only by surfacing truthful evidence already present in candidate details or source documents.
5. Rewrite weak bullets as action + tool/method + result/business purpose.
6. Keep ATS-safe formatting: plain headings, plain bullets, no tables, no icons, no decorative separators.
7. Preserve real contact details at the top.
8. Remove duplicate, irrelevant, weak, or unsupported content.
9. Keep the resume concise. Keep the CV complete but still focused.

Use non-thinking mode. /no_think
""".strip()

        user_input = f"""
TARGET DOCUMENT TYPE:
{request.document_type}

CANDIDATE EVIDENCE:
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

CURRENT GENERATED DOCUMENT:
{generated_document}

HEURISTIC QUALITY REPORT:
{heuristic_report}

AI QUALITY REVIEW:
{ai_review or "No AI quality review supplied. Use the heuristic report."}

TASK:
Return only the improved {request.document_type}. No commentary. No code fence.
""".strip()
        return instructions, user_input

    def _generate_local_draft(self, request: GenerationRequest, note: str = "AI was not used for this draft.") -> str:
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
            f"- {note}",
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
