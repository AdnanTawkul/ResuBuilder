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
    links: str = ""
    general_cv: str = ""
    general_resume: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class GenerationRequest:
    profile: CandidateProfile
    job_description: str
    template_name: str
    document_type: str
