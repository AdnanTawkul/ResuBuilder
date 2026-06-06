from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class CandidateProfile:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    title: str = ""
    summary: str = ""
    studies: str = ""
    professions: str = ""
    projects: str = ""
    skills: str = ""
    languages: str = ""
    structured_evidence: str = ""
    links: str = ""
    general_cv: str = ""
    general_cover_letter: str = ""
    # Legacy field kept so old saved profiles/workspaces that used “general_resume” still load safely.
    general_resume: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class AISettings:
    use_ai: bool = True
    provider: str = "Ollama Local"
    api_key: str = ""
    model: str = "gpt-4.1-mini"
    generation_mode: str = "Balanced"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    timeout_seconds: int = 120


@dataclass
class GenerationRequest:
    profile: CandidateProfile
    job_description: str
    template_name: str
    document_type: str
    ai_settings: AISettings
