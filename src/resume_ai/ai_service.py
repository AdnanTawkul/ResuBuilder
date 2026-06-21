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
    DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b").strip() or "qwen3:8b"
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

    def analyze_job_fit(
        self,
        profile,
        job_description: str,
        settings: AISettings,
        target_company: str = "",
        target_role: str = "",
    ) -> str:
        """Uses Ollama to analyze fit before generation so the app does not write blind drafts."""
        if not settings.use_ai:
            return "Job fit analysis failed: AI is disabled in the AI Settings tab."

        job_signals = extract_job_keywords(job_description, limit=28)
        supported_signals, unsupported_signals = split_keywords_by_candidate_evidence(job_signals, profile)
        evidence_map = self._build_evidence_map(profile, job_signals)
        truth_aware_signal_report = build_truth_aware_signal_report(profile, job_description, limit=28)
        project_candidate_summary = self._project_candidate_summary(profile)

        instructions = """
/no_think
You are a strict job-fit strategist for CV and covering-letter generation.
Use Ollama/local reasoning to compare the candidate evidence against the target job before any document is generated.
Output clean Markdown only. Do not wrap the answer in code fences.
Do not reveal chain-of-thought, hidden reasoning, thinking notes, analysis notes, or implementation details.

Hard rules:
1. Never invent experience, clients, employers, metrics, tools, publications, degrees, dates, or achievements.
2. Separate strong alignment from weak alignment and unsupported gaps.
3. Do not recommend adding a job keyword unless the candidate evidence supports it.
4. Be blunt when the job is a weak fit.
5. Give practical generation strategy for both the CV and covering letter.
6. Include a fit score from 0 to 100 based on truthful evidence, not optimism.

Required Markdown structure:
# Job Fit Analysis

**Fit Score:** NN/100
**Verdict:** one direct sentence

## Strong alignment
- supported signal: evidence source

## Weak alignment
- weak signal: what evidence is thin or indirect

## Unsupported or risky claims
- signal: do not claim this unless new evidence is added

## Recommended CV strategy
- how to position the CV truthfully

## Recommended covering letter strategy
- how to position the covering letter truthfully

## Evidence gaps to fill
- exact evidence the user should add to improve fit

## Generation instructions
- concise instructions that the CV/covering-letter generator should follow
""".strip()

        user_input = f"""
TARGET COMPANY:
{target_company or "Not specified"}

TARGET ROLE:
{target_role or profile.title or "Not specified"}

CANDIDATE DETAILS:
Name: {profile.name}
Current or target title: {profile.title}
Location: {profile.location}

Professional summary:
{profile.summary}

Studies / education:
{profile.studies}

Professions / work experience:
{profile.professions}

Projects:
{profile.projects}

Project candidates and selection notes:
{project_candidate_summary}

Skills:
{profile.skills}

Languages:
{profile.languages}

Structured evidence:
{getattr(profile, "structured_evidence", "")}

Existing CV:
{profile.general_cv}

Existing covering letter:
{profile.general_cover_letter or profile.general_resume}

EXTRACTED JOB SIGNALS:
{', '.join(job_signals) if job_signals else 'No strong job signals detected.'}

SUPPORTED SIGNALS FROM CURRENT EVIDENCE:
{', '.join(supported_signals) if supported_signals else 'None clearly supported yet.'}

UNSUPPORTED SIGNALS FROM CURRENT EVIDENCE:
{', '.join(unsupported_signals) if unsupported_signals else 'None clearly unsupported.'}

TRUTH-AWARE SIGNAL REPORT:
{truth_aware_signal_report}

EVIDENCE MAP:
{evidence_map}

TARGET JOB DESCRIPTION:
{job_description}
""".strip()

        # This feature intentionally uses Ollama. If the user selected OpenAI elsewhere, job-fit analysis still runs locally.
        ollama_settings = AISettings(
            use_ai=settings.use_ai,
            provider=self.PROVIDER_OLLAMA,
            api_key="",
            model=settings.model,
            generation_mode=settings.generation_mode,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model or self.DEFAULT_OLLAMA_MODEL,
            timeout_seconds=settings.timeout_seconds,
        )
        try:
            response = self._call_ollama_chat(
                settings=ollama_settings,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user_input},
                ],
                timeout=float(settings.timeout_seconds or 180),
                num_predict=2400,
            )
            text = self._extract_ollama_text(response).strip()
            if not text:
                return "Ollama returned an empty job fit analysis. Add more evidence or try again."
            return self._clean_local_model_output(text)
        except Exception as exc:
            return f"Ollama job fit analysis failed: {exc}"

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
- Apply the project-selection rules below. Do not dump every project into the CV.
""".strip()

        project_selection_guidance = self._project_selection_guidance(request)
        project_candidate_summary = self._project_candidate_summary(profile)
        skill_selection_guidance = self._skill_selection_guidance(request)

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

Project-selection rules:
{project_selection_guidance}

Skill-selection rules:
{skill_selection_guidance}

Required structure:
{required_structure}

High-priority job signals extracted from the job description:
{', '.join(job_signals) if job_signals else 'No strong job signals detected. Use the candidate evidence and target title.'}

Truth-aware signal report:
{truth_aware_signal_report}

Candidate evidence map:
{evidence_map}

Job fit analysis and generation strategy:
{request.job_fit_analysis.strip() or 'No pre-generation job fit analysis supplied. Generate from the truth-aware signal report and candidate evidence.'}

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

Project candidates and selection notes:
{project_candidate_summary}

Project-selection rules:
{project_selection_guidance}

Skill-selection rules:
{skill_selection_guidance}

Skills inventory supplied by the candidate:
{profile.skills}

Languages:
{profile.languages}

Structured evidence:
{getattr(profile, "structured_evidence", "")}

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

JOB FIT ANALYSIS / GENERATION STRATEGY:
{request.job_fit_analysis.strip() or 'No job fit analysis supplied.'}

PRIMARY EXISTING SOURCE DOCUMENT:
{source_document}

SECONDARY EXISTING SOURCE DOCUMENT:
{alternate_source}

TARGET JOB DESCRIPTION:
{request.job_description}

FINAL SKILL-SELECTION CHECK BEFORE WRITING:
Before producing the final CV, verify that the Core Skills section is not copied from generic job signals or the quality report. It must be selected from the candidate's own skills inventory and evidence. Remove weak generic words such as customer, research, training, models, and software engineering when they stand alone. Prefer precise technical skills, tools, methods, and evaluation concepts that match the target job.

FINAL PROJECT-SELECTION CHECK BEFORE WRITING:
Before producing the final CV, verify that the Projects section contains the strongest available project candidates for this job. If a defence, signal intelligence, RF/IQ, robustness, deployment, or mission-critical AI project is available and the job context matches those signals, include it unless three projects are clearly more directly relevant.
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
        project_selection_guidance = self._project_selection_guidance(request)
        project_candidate_summary = self._project_candidate_summary(profile)
        skill_selection_guidance = self._skill_selection_guidance(request)

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
7. For a CV, judge scannability, evidence strength, ATS safety, role alignment, whether the Core Skills section uses strong job-relevant technical skills, and whether the Projects section selected the strongest available projects for the target job.
8. If the candidate supplied at least 3 truthful project candidates, the CV should include at least 3 relevant projects ordered from strongest fit to weaker fit.
9. Flag weak skills sections that copy generic job signals such as customer, research, training, models, or software engineering instead of selecting precise skills from the candidate's actual skills inventory.
10. Be direct and specific.
11. Flag when a strategically relevant project was omitted, especially RF/signal intelligence, sensor/signal processing, robustness, deployment, or research-engineering projects for defence or mission-critical AI roles.

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

Structured evidence:
{getattr(profile, "structured_evidence", "")}

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

JOB FIT ANALYSIS / GENERATION STRATEGY:
{request.job_fit_analysis.strip() or 'No job fit analysis supplied.'}

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
- Rebuild the Core Skills section from the candidate's real skills inventory, not from generic job-signal words.
- Keep ATS-safe formatting: plain headings, plain bullets, no tables, no icons, no decorative separators.
- Remove duplicate, irrelevant, weak, or unsupported content.
- Keep relevant depth, but cut anything that dilutes the target role.
- Re-evaluate the Projects section. Keep at least 3 truthful project entries when available, ordered by relevance to the target job.
""".strip()

        project_selection_guidance = self._project_selection_guidance(request)
        project_candidate_summary = self._project_candidate_summary(profile)
        skill_selection_guidance = self._skill_selection_guidance(request)

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

Project-selection rules:
{project_selection_guidance}

Skill-selection rules:
{skill_selection_guidance}

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

Project candidates and selection notes:
{project_candidate_summary}

Project-selection rules:
{project_selection_guidance}

Skill-selection rules:
{skill_selection_guidance}

Skills inventory supplied by the candidate:
{profile.skills}

Languages:
{profile.languages}

Structured evidence:
{getattr(profile, "structured_evidence", "")}

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

JOB FIT ANALYSIS / GENERATION STRATEGY:
{request.job_fit_analysis.strip() or 'No job fit analysis supplied.'}

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
If this is a CV, rebuild weak Core Skills sections that contain generic terms like customer, research, training, models, or software engineering. Use precise skills from the candidate's real skills inventory and evidence, selected for the target job. If this is a CV and the current Projects section omitted a stronger supplied project, replace the weakest selected project with the stronger one. For defence or mission-critical AI jobs, treat RF/signal intelligence, raw IQ/sensor processing, robustness, channel-shift detection, and deployment inference as strategically relevant.
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
12 to 20 concise, truthful, job-relevant skills selected from the candidate's supplied skills inventory. Prefer concrete tools, frameworks, methods, model types, data workflows, and evaluation concepts. Do not copy generic job signals such as customer, research, training, models, or software engineering as standalone skills.

## Education
Degree, school, dates, focus areas.

## Professional Experience
### Role | Organization | Location | Dates
- Action + tool/method/domain detail + result or technical purpose.

## Projects
### Project Name
- Tools/methods used and why they matter for the target job.
- Outcome, evaluation, technical purpose, or proof.

Include at least 3 truthful project entries when 3 or more are supplied. Order them from best job fit to weaker job fit. Omit irrelevant extra projects unless needed to reach the minimum 3.

## Languages
Only when supplied."""
        return """# Candidate Name
Title
Email: name@example.com | Phone: number | Location: city
Links: portfolio/linkedin/github

## Professional Summary
2 to 3 lines focused on the target role.

## Core Skills
12 to 20 concise, truthful, job-relevant skills selected from the candidate's supplied skills inventory. Prefer concrete tools, frameworks, methods, model types, data workflows, and evaluation concepts. Do not copy generic job signals such as customer, research, training, models, or software engineering as standalone skills.

## Professional Experience
### Role | Organization | Location | Dates
- Action + tool/method/domain detail + result or technical purpose.

## Projects
### Project Name
- Tools/methods used and why they matter for the target job.
- Outcome, evaluation, technical purpose, or proof.

Include at least 3 truthful project entries when 3 or more are supplied. Order them from best job fit to weaker job fit. Omit irrelevant extra projects unless needed to reach the minimum 3.

## Education
Degree, school, dates, focus areas."""


    def _skill_selection_guidance(self, request: GenerationRequest) -> str:
        """Guidance for selecting a strong but compact CV skills section."""
        job_text = (getattr(request, "job_description", "") or "").lower()
        foundation_context = any(
            token in job_text
            for token in [
                "foundation model", "foundational model", "llm", "vlm", "vision-language", "multimodal",
                "transformer", "attention", "fine-tuning", "finetuning", "distributed training", "gpu cluster",
                "data curation", "data cleaning", "data pruning", "large-scale",
            ]
        )
        defence_context = any(
            token in job_text
            for token in [
                "defence", "defense", "helsing", "sovereign", "mission-critical", "mission critical",
                "signal", "signals", "sensor", "sensors", "rf", "iq", "radio", "autonomous", "robust",
                "deployment", "distribution shift", "channel shift",
            ]
        )

        base = (
            "For a CV Core Skills section, do not copy the extracted job signals, quality-report signals, or vague words. "
            "Select 12 to 20 compact skills from the candidate's supplied skills inventory and structured evidence. "
            "Prefer precise skills that a recruiter can search for: languages, frameworks, model families, ML methods, data workflows, "
            "evaluation metrics, signal/image-processing methods, deployment tools, and reproducibility practices. "
            "Avoid weak standalone terms such as customer, research, training, models, software engineering, hard working, communication, or team player. "
            "Use those concepts only when made specific, for example model training, reproducible ML workflows, or technical communication. "
            "Do not list every supplied skill. Keep the section targeted, compact, and ATS-friendly. "
            "A good format is one comma-separated line or 2 short grouped lines, not a long paragraph."
        )
        if foundation_context:
            base += (
                " For foundation-model, LLM/VLM, or multimodal AI roles, prioritize truthful adjacent skills such as Python, PyTorch, "
                "deep learning, CNNs, self-supervised learning, transfer learning, model adaptation, custom loss functions, optical flow, "
                "data curation, model evaluation, AUC-ROC, F1-score, error analysis, reproducible ML workflows, CUDA, and Git/GitHub. "
                "Do not claim transformers, attention mechanisms, LLM training, VLM fine-tuning, JAX, or distributed training unless the candidate evidence explicitly supports them."
            )
        if defence_context:
            base += (
                " For defence, sensor, signal, RF, robustness, or deployment-focused roles, also prioritize truthful skills such as raw IQ signal processing, "
                "RF modulation recognition, channel-shift detection, robustness evaluation, deployment inference, Streamlit, JSON/CSV exports, and CUDA inference."
            )
        return base

    def _project_selection_guidance(self, request: GenerationRequest) -> str:
        job_text = (getattr(request, "job_description", "") or "").lower()
        defence_context = any(
            token in job_text
            for token in [
                "defence", "defense", "helsing", "sovereign", "mission-critical", "mission critical",
                "signal", "signals", "sensor", "sensors", "rf", "iq", "radio", "autonomous", "robotics",
                "robust", "deployment", "distribution shift", "channel shift",
            ]
        )

        if self._is_cover_letter(request.document_type):
            base = (
                "For a covering letter, do not list many projects. Select only the 1 to 2 strongest project examples "
                "that match the target job, and mention them briefly as proof. Never invent a project or claim."
            )
            if defence_context:
                base += (
                    " When the target role involves defence, mission-critical AI, signals, sensors, robustness, or deployment, "
                    "prefer project examples involving RF/signal intelligence, raw sensor or signal data, robustness evaluation, "
                    "distribution/channel shift, GPU inference, or research-to-application delivery over generic examples."
                )
            return base

        if (request.document_type or "").strip().lower() == "cv":
            base = (
                "For the CV Projects section, rank supplied project candidates by relevance to the target job. "
                "Use job responsibilities, required skills, job-fit analysis, supported job signals, tools, domain, evidence strength, "
                "and strategic domain relevance. Do not rely only on exact keyword overlap. "
                "Include at least 3 truthful project entries when 3 or more project candidates are supplied. "
                "If fewer than 3 truthful project candidates are supplied, include all available projects and do not invent additional projects. "
                "Order projects from strongest job fit to weaker job fit. "
                "Omit irrelevant extra projects beyond the best 3 unless they add clear value for the target role. "
                "Use ### Project Name headings with 2 to 4 concise bullets so the PDF exporter can keep project blocks together where possible. "
                "Do not include a project only because it sounds impressive; include it because it supports the target job. "
                "If a supplied project is a stronger fit than one already chosen, replace the weaker project rather than adding a fourth project by default."
            )
            if defence_context:
                base += (
                    " Defence/mission-critical AI special rule: when the target company or role mentions defence, mission impact, "
                    "sovereign technology, signals, sensors, robustness, deployment, or AI systems, treat RF signal intelligence, "
                    "raw IQ/sensor processing, modulation recognition, channel-shift detection, robustness experiments, GPU inference, "
                    "and research-to-application engineering as high-priority evidence. A project titled or described as RF Signal Intelligence Lab, "
                    "RF modulation recognition, raw IQ signal processing, signal intelligence, channel-shift detection, or deployment inference "
                    "should normally be included in the top 3 unless there are at least 3 projects with more direct foundation-model, LLM/VLM, "
                    "transformer, distributed-training, or multimodal evidence. For a Helsing-style defence AI role, prefer RF Signal Intelligence Lab "
                    "over weaker biomedical or generic validation projects when both are available."
                )
            return base

        return (
            "Select evidence by relevance to the target job. Do not include irrelevant projects or unsupported claims. "
            "Consider strategic domain relevance, not only exact keyword overlap."
        )

    def _project_candidate_summary(self, profile) -> str:
        plain_projects = (getattr(profile, "projects", "") or "").strip()
        structured_evidence = (getattr(profile, "structured_evidence", "") or "").strip()

        notes = []
        if plain_projects:
            notes.append("Plain Projects field candidates:\n" + plain_projects)
        if structured_evidence:
            notes.append(
                "Structured evidence candidates. Prioritize entries where Type is Project, but work achievements may be used if they are more relevant than weak projects:\n"
                + structured_evidence
            )
        if not notes:
            return (
                "No explicit project candidates were supplied. If the CV requires a Projects section, use only truthful project-like evidence from work experience or studies. "
                "If fewer than 3 truthful project-like examples exist, include fewer and do not invent."
            )
        return "\n\n---\n\n".join(notes)

    def _build_evidence_map(self, profile, job_signals: list[str]) -> str:
        source = "\n".join([
            profile.summary,
            profile.studies,
            profile.professions,
            profile.projects,
            profile.skills,
            profile.languages,
            getattr(profile, "structured_evidence", ""),
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
