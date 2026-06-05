from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from .models import AISettings, GenerationRequest
from .templates import get_template
from .quality_checker import extract_job_keywords, build_truth_aware_signal_report, split_keywords_by_candidate_evidence


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
                return self._postprocess_generated_document(text, request)
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
                return self._postprocess_generated_document(text, request) if text else "OpenAI returned an empty improved document."
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

    def _is_cover_letter(self, document_type: str) -> bool:
        normalized = (document_type or "").strip().lower().replace("_", "-")
        return normalized in {"covering letter", "cover letter", "cover-letter", "covering-letter"}

    def _source_documents_for_request(self, request: GenerationRequest) -> tuple[str, str]:
        profile = request.profile
        if request.document_type.lower() == "cv":
            primary = profile.general_cv
            secondary = profile.general_cover_letter or profile.general_resume
        elif self._is_cover_letter(request.document_type):
            primary = profile.general_cover_letter or profile.general_resume
            secondary = profile.general_cv
        else:
            primary = profile.general_cover_letter or profile.general_resume
            secondary = profile.general_cv
        return primary, secondary

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
            return self._postprocess_generated_document(text, request)
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
            return self._postprocess_generated_document(text, request)
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
                "top_p": 0.85,
                "repeat_penalty": 1.08,
                "num_predict": int(num_predict),
                "num_ctx": 12288,
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

    def _postprocess_generated_document(self, text: str, request: GenerationRequest) -> str:
        """Clean model artifacts and enforce minimum career-document structure."""
        cleaned = self._clean_local_model_output(text)
        cleaned = self._strip_non_document_preface(cleaned)
        cleaned = self._ensure_contact_header(cleaned, request)
        return cleaned.strip()

    def _strip_non_document_preface(self, text: str) -> str:
        cleaned = text.strip()
        lower = cleaned.lower()
        for marker in ["# ", "## "]:
            idx = lower.find(marker)
            if idx > 0 and any(bad in lower[:idx] for bad in ["here is", "here's", "improved", "tailored", "resume", "cv"]):
                cleaned = cleaned[idx:].strip()
                lower = cleaned.lower()
                break
        cleaned = re.sub(r"^\s*(here is|here's)\b.*?\n+", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        return cleaned

    def _ensure_contact_header(self, text: str, request: GenerationRequest) -> str:
        profile = request.profile
        cleaned = text.strip()
        lower = cleaned.lower()
        digits = re.sub(r"\D", "", cleaned)
        phone_digits = re.sub(r"\D", "", profile.phone or "")

        missing_name = bool(profile.name and profile.name.lower() not in lower[:500])
        missing_email = bool(profile.email and profile.email.lower() not in lower[:700])
        missing_phone = bool(phone_digits and phone_digits not in digits[:900])
        missing_heading = not bool(re.search(r"^#{1,2}\s+", cleaned, flags=re.MULTILINE))

        if not (missing_name or missing_email or missing_phone or missing_heading):
            return cleaned

        header_lines = []
        header_lines.append(f"# {profile.name or 'Candidate'}")
        if profile.title:
            header_lines.append(profile.title)

        contact_parts = []
        if profile.email:
            contact_parts.append(f"Email: {profile.email}")
        if profile.phone:
            contact_parts.append(f"Phone: {profile.phone}")
        if profile.location:
            contact_parts.append(f"Location: {profile.location}")
        if contact_parts:
            header_lines.append(" | ".join(contact_parts))
        if profile.links:
            header_lines.append(f"Links: {profile.links}")

        header = "\n".join(header_lines).strip()
        # If the model already started with the candidate name but forgot contact details, replace only the first loose name line.
        if profile.name and cleaned.lower().startswith(profile.name.lower()):
            cleaned = re.sub(r"^" + re.escape(profile.name) + r"\s*\n*", "", cleaned, count=1, flags=re.IGNORECASE).strip()
        return f"{header}\n\n{cleaned}".strip()

    def _temperature_for_mode(self, mode: str) -> float:
        normalized = (mode or "Balanced").strip().lower()
        if normalized == "conservative":
            return 0.15
        if normalized == "aggressive":
            return 0.45
        return 0.25

    def _build_generation_prompt(self, request: GenerationRequest) -> tuple[str, str]:
        profile = request.profile
        template = get_template(request.template_name)
        mode = request.ai_settings.generation_mode.strip() or "Balanced"
        source_document, alternate_source = self._source_documents_for_request(request)
        job_signals = extract_job_keywords(request.job_description, limit=24)
        supported_signals, unsupported_signals = split_keywords_by_candidate_evidence(job_signals, profile)
        evidence_map = self._build_evidence_map(profile, job_signals)
        truth_aware_signal_report = build_truth_aware_signal_report(profile, request.job_description, limit=24)
        required_structure = self._required_document_structure(request.document_type)
        is_cover_letter = self._is_cover_letter(request.document_type)

        if is_cover_letter:
            document_guidance = """
Covering letter guidance:
- Write a concise covering letter, not a resume in paragraph form.
- Use 3 to 5 short paragraphs.
- Start by naming the target role/company when the job description provides enough context.
- Connect motivation to truthful candidate evidence, not generic enthusiasm.
- Include 2 to 3 proof points that match supported job signals.
- Close with a confident but plain call to discuss fit.
- Do not use bullet-heavy resume sections unless the user supplied a covering-letter source that already uses them.
""".strip()
        else:
            document_guidance = """
CV guidance:
- Use scannable sections and truthful achievement bullets.
- Every bullet should contain an action, a tool/method/domain detail, and a business or technical purpose where truthful.
- Remove weak, irrelevant, repetitive, or outdated information.
- Make the first third of the document the strongest part.
""".strip()

        instructions = f"""
/no_think
You are an expert career document strategist.
Create a tailored {request.document_type} for the target job.
Output the final document only, in clean Markdown. Do not wrap the answer in code fences.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, analysis notes, or implementation details.

Hard rules:
1. Never invent employers, degrees, dates, certifications, tools, metrics, titles, publications, grants, clients, or achievements.
2. Never omit supplied contact details. The first lines must include name, email, phone, and location when supplied.
3. Use simple Markdown. No tables, no icons, no decorative separators, no code fences.
4. Use only job keywords that are supported by candidate evidence.
5. If a job keyword is not supported by candidate evidence, do not force it into the document.
6. Do not write generic motivational language such as passionate, excited, fantastic opportunity, team player, or hardworking.
7. Return only the completed {request.document_type}. No explanation before or after it.

Document-specific guidance:
{document_guidance}

Required structure:
{required_structure}

High-priority job signals extracted from the job description:
{', '.join(job_signals) if job_signals else 'No strong job signals detected. Use the candidate evidence and target title.'}

Truth-aware signal report:
{truth_aware_signal_report}

Candidate evidence map:
{evidence_map}

Template style: {request.template_name}
Template purpose: {template['description']}
Tone: {template['tone']}
Generation mode: {mode}

Mode guidance:
- Conservative: preserve the candidate's original facts and wording more closely.
- Balanced: improve clarity, ordering, impact, and keyword alignment without overreaching.
- Aggressive: sharpen positioning but still do not invent facts.
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

JOB SIGNALS TO USE ONLY IF SUPPORTED:
{', '.join(job_signals) if job_signals else 'None detected'}

SUPPORTED SIGNALS TO SURFACE:
{', '.join(supported_signals) if supported_signals else 'None clearly supported yet'}

UNSUPPORTED SIGNALS TO AVOID UNLESS USER ADDS TRUTHFUL EVIDENCE:
{', '.join(unsupported_signals) if unsupported_signals else 'None'}

TRUTH-AWARE SIGNAL REPORT:
{truth_aware_signal_report}

EVIDENCE MAP:
{evidence_map}

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
        source_document, alternate_source = self._source_documents_for_request(request)
        job_signals = extract_job_keywords(request.job_description, limit=24)
        supported_signals, unsupported_signals = split_keywords_by_candidate_evidence(job_signals, profile)
        evidence_map = self._build_evidence_map(profile, job_signals)
        truth_aware_signal_report = build_truth_aware_signal_report(profile, request.job_description, limit=24)
        required_structure = self._required_document_structure(request.document_type)

        instructions = f"""
You are a strict career document quality reviewer.
Review the generated {request.document_type} against the target job and the candidate evidence.
Output clean Markdown only. Do not wrap the answer in code fences.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, or implementation details.

Hard rules:
1. Do not rewrite the full document. Review it.
2. Identify unsupported claims, fake-looking metrics, placeholders, weak evidence, and keyword gaps.
3. Do not suggest adding a keyword unless it is truthful based on candidate evidence.
4. Separate missing supported signals from unsupported job-fit gaps.
5. Say clearly when regeneration cannot improve the score without more candidate evidence.
6. For a covering letter, judge role fit, company alignment, concrete proof, tone, and concise structure.
7. For a CV, judge scannability, evidence strength, ATS safety, and role alignment.
8. Be direct and specific.

Required Markdown sections:
# AI Quality Review
## Critical risks
## Missing or weak evidence
## Keyword alignment
## Structure and formatting
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

JOB SIGNALS TO USE ONLY IF SUPPORTED:
{', '.join(job_signals) if job_signals else 'None detected'}

SUPPORTED SIGNALS TO SURFACE:
{', '.join(supported_signals) if supported_signals else 'None clearly supported yet'}

UNSUPPORTED SIGNALS TO AVOID UNLESS USER ADDS TRUTHFUL EVIDENCE:
{', '.join(unsupported_signals) if unsupported_signals else 'None'}

TRUTH-AWARE SIGNAL REPORT:
{truth_aware_signal_report}

EVIDENCE MAP:
{evidence_map}

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
        source_document, alternate_source = self._source_documents_for_request(request)
        job_signals = extract_job_keywords(request.job_description, limit=24)
        supported_signals, unsupported_signals = split_keywords_by_candidate_evidence(job_signals, profile)
        evidence_map = self._build_evidence_map(profile, job_signals)
        truth_aware_signal_report = build_truth_aware_signal_report(profile, request.job_description, limit=24)
        required_structure = self._required_document_structure(request.document_type)
        is_cover_letter = self._is_cover_letter(request.document_type)

        if is_cover_letter:
            document_guidance = """
Covering letter improvement priorities:
- Keep it concise, usually 250 to 450 words.
- Use a real letter flow: opening, fit evidence, company/role alignment, closing.
- Improve supported job-signal alignment through truthful examples, not keyword stuffing.
- Use first person where natural, but avoid needy, generic, or exaggerated language.
- Do not turn the covering letter into a resume with many bullets.
""".strip()
        else:
            document_guidance = """
CV improvement priorities:
- Rewrite weak bullets as action + tool/method + result/business purpose.
- Keep ATS-safe formatting: plain headings, plain bullets, no tables, no icons, no decorative separators.
- Remove duplicate, irrelevant, weak, or unsupported content.
- Keep relevant depth, but cut anything that dilutes the target role.
""".strip()

        instructions = f"""
You are an expert career document editor.
Rewrite the current {request.document_type} using the quality report as constraints.
Output the improved {request.document_type} only, in clean Markdown.
Do not wrap the answer in code fences.
Do not include analysis, notes, explanations, or quality-review commentary.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, or implementation details.

Hard rules:
1. Never invent employers, clients, projects, degrees, dates, certifications, metrics, tools, titles, or achievements.
2. Do not add consulting, DevOps, ETL, REST, cloud, architecture, embedded, audio, or client-facing claims unless the candidate evidence clearly supports them.
3. If the job uses a keyword but the candidate evidence does not support it, omit the keyword instead of faking alignment.
4. Improve keyword alignment only by surfacing truthful evidence already present in candidate details or source documents.
5. Prioritize missing supported signals over unsupported job-fit gaps.
6. If a quality report lists unsupported job signals, do not chase them. Improve the document around supported signals, contact, structure, ordering, and evidence.
7. Preserve real contact details at the top.
8. Return only the improved document.

Document-specific guidance:
{document_guidance}

Required structure:
{required_structure}

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

JOB SIGNALS TO USE ONLY IF SUPPORTED:
{', '.join(job_signals) if job_signals else 'None detected'}

SUPPORTED SIGNALS TO SURFACE:
{', '.join(supported_signals) if supported_signals else 'None clearly supported yet'}

UNSUPPORTED SIGNALS TO AVOID UNLESS USER ADDS TRUTHFUL EVIDENCE:
{', '.join(unsupported_signals) if unsupported_signals else 'None'}

TRUTH-AWARE SIGNAL REPORT:
{truth_aware_signal_report}

EVIDENCE MAP:
{evidence_map}

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

    def _required_document_structure(self, document_type: str) -> str:
        if self._is_cover_letter(document_type):
            return """# Candidate Name
Title
Email: name@example.com | Phone: number | Location: city
Links: portfolio/linkedin/github

Dear Hiring Team,

Opening paragraph: name the target role/company when clear and state the strongest truthful fit.

Evidence paragraph: connect 1 to 2 relevant experiences, projects, tools, or domains to the job.

Role-alignment paragraph: explain why this role/company is a logical next step without generic flattery.

Closing paragraph: concise call to discuss fit.

Sincerely,
Candidate Name"""
        if (document_type or "").lower() == "cv":
            return """# Candidate Name
Title
Email: name@example.com | Phone: number | Location: city
Links: portfolio/linkedin/github

## Professional Summary
2 to 4 lines focused on the target role.

## Core Skills
Plain comma-separated or short bullet list of truthful skills.

## Education
Degree, school, dates, focus areas.

## Professional Experience
### Role | Organization | Location | Dates
- Action + tool/method/domain detail + result or technical purpose.

## Projects
- Project + tools/methods + outcome or purpose.

## Languages
Only when supplied."""
        return """# Candidate Name
Title
Email: name@example.com | Phone: number | Location: city
Links: portfolio/linkedin/github

## Professional Summary
2 to 3 lines focused on the target role.

## Core Skills
Plain comma-separated or short bullet list of truthful skills.

## Professional Experience
### Role | Organization | Location | Dates
- Action + tool/method/domain detail + result or technical purpose.

## Projects
- Project + tools/methods + outcome or purpose.

## Education
Degree, school, dates, focus areas."""

    def _build_evidence_map(self, profile, job_signals: list[str]) -> str:
        source = "\n".join([
            profile.summary,
            profile.studies,
            profile.professions,
            profile.projects,
            profile.skills,
            profile.languages,
            profile.general_cv,
            profile.general_cover_letter,
            profile.general_resume,
        ]).lower()
        if not job_signals:
            return "No extracted job signals. Rely on supplied candidate details only."

        support_variants = {
            "api": {"api", "apis", "rest"},
            "rest api": {"rest", "api", "apis", "rest api"},
            "deep learning": {"deep learning", "neural", "tensorflow", "pytorch", "model"},
            "machine learning": {"machine learning", "ml", "model", "tensorflow", "pytorch"},
            "computer vision": {"computer vision", "image processing", "opencv", "microscopy"},
            "audio processing": {"audio", "audio processing", "audio signal processing", "speech", "speech processing"},
            "audio": {"audio", "audio processing", "speech", "speech processing"},
            "signal processing": {"signal processing", "eeg", "audio", "time series"},
            "models": {"model", "models", "deep learning", "machine learning", "tensorflow", "pytorch", "neural"},
            "algorithms": {"algorithm", "algorithms", "computer vision", "image processing", "deep learning"},
            "research": {"research", "thesis", "study", "evaluated", "investigated", "experiment"},
            "training": {"training", "trained", "model training", "tensorflow", "pytorch"},
            "quality": {"quality", "validation", "testing", "qa", "reliability", "validated"},
            "embedded": {"embedded", "hardware", "device", "devices", "sensor", "wearable", "edge"},
            "embedded systems": {"embedded", "hardware", "device", "devices", "sensor", "wearable", "edge"},
        }

        lines = []
        for signal in job_signals[:24]:
            variants = {signal.lower(), signal.lower().replace("-", " ")}
            variants.update(support_variants.get(signal.lower(), set()))
            supported = any(v and v in source for v in variants)
            lines.append(f"- {signal}: {'supported by candidate evidence' if supported else 'not clearly supported, do not force'}")
        return "\n".join(lines)

    def _generate_local_draft(self, request: GenerationRequest, note: str = "AI was not used for this draft.") -> str:
        profile = request.profile
        template = get_template(request.template_name)
        keywords = self._extract_keywords(request.job_description)

        if self._is_cover_letter(request.document_type):
            return self._generate_local_cover_letter_draft(request, note=note)

        heading = "Tailored CV" if request.document_type.lower() == "cv" else f"Tailored {request.document_type}"
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

    def _generate_local_cover_letter_draft(self, request: GenerationRequest, note: str) -> str:
        profile = request.profile
        keywords = self._extract_keywords(request.job_description)
        focus = ", ".join(keywords[:5]) if keywords else "the target role"
        evidence = profile.projects.strip() or profile.professions.strip() or profile.summary.strip() or "Add concrete project or work evidence before sending this letter."
        lines = [
            f"# {profile.name or 'Your Name'}",
            f"{profile.title or 'Target Title'}",
            f"Email: {profile.email} | Phone: {profile.phone} | Location: {profile.location}",
            f"Links: {profile.links}" if profile.links else "",
            "",
            "Dear Hiring Team,",
            "",
            f"I am applying for the target role because my background aligns with {focus}. {profile.summary.strip() or 'My experience combines technical work, structured problem solving, and delivery-focused execution.'}",
            "",
            f"The strongest evidence from my background is: {evidence}",
            "",
            "I would welcome the opportunity to discuss how this experience can support your team. This draft needs manual editing before submission because it was created without AI generation.",
            "",
            "Sincerely,",
            profile.name or "Your Name",
            "",
            "## Drafting Notes",
            f"- {note}",
            "- Replace generic wording with specific role/company alignment.",
            "- Add only truthful evidence from your actual experience.",
        ]
        return "\n".join(line for line in lines if line is not None).strip()

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
        return extract_job_keywords(job_description, limit=12)
