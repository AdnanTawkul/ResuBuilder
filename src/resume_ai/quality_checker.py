from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
import re

from .models import CandidateProfile


STOPWORDS = {
    "about", "above", "after", "again", "against", "also", "among", "and", "any", "are", "because",
    "been", "before", "being", "below", "between", "both", "but", "can", "did", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "here", "hers", "him", "his", "how", "into", "its", "itself", "just", "more", "most", "not",
    "off", "once", "only", "other", "our", "ours", "out", "over", "own", "same", "she", "should",
    "some", "such", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "too", "under", "until", "very", "was", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "you", "your", "role", "work", "team",
    "job", "candidate", "company", "experience", "skills", "ability", "requirements", "required", "preferred",
    "need", "needs", "looking", "seeking", "must", "plus", "using", "based", "within", "join", "joining",
    "responsibility", "responsibilities", "include", "includes", "including", "provide", "provides", "provided",
    "excited", "fantastic", "opportunity", "today", "form", "core", "range", "wide", "full", "premium",
    "optimal", "great", "excellent", "strong", "good", "new", "novel", "state", "art", "of-the-art",
    "develop", "development", "developing", "developer", "engineer", "engineers", "engineering", "people",
    "culture", "values", "mission", "growth", "path", "career", "interests", "strengths", "audatic",
}

# Terms here should be job-signal terms, not generic job-posting prose.
# This list intentionally over-indexes on technical resume jobs because the app is currently tested on AI/software roles.
SKILL_PHRASES = [
    "python", "sql", "excel", "power bi", "tableau", "machine learning", "deep learning",
    "data analysis", "data science", "statistics", "automation", "computer vision", "image processing",
    "signal processing", "audio processing", "audio", "speech", "nlp", "natural language processing",
    "model training", "training", "neural networks", "algorithms", "research", "state-of-the-art models",
    "models", "embedded", "embedded systems", "edge ai", "inference", "optimization", "pytorch", "tensorflow",
    "opencv", "scikit-learn", "pandas", "numpy", "matlab", "api", "apis", "rest", "rest api",
    "fastapi", "flask", "django", "tkinter", "pyqt", "desktop applications", "gui", "git", "github",
    "docker", "kubernetes", "aws", "azure", "gcp", "linux", "windows", "testing", "unit testing",
    "pytest", "validation", "quality", "qa", "agile", "scrum", "stakeholder", "client", "clients",
    "customer", "consulting", "consultant", "project management", "leadership", "communication",
    "technical documentation", "devops", "ci/cd", "etl", "data pipeline", "data pipelines", "cloud",
    "architecture", "fullstack", "full-stack", "backend", "frontend", "software engineering",
]

# Fallback single-token terms allowed from job descriptions. Anything not here is usually boilerplate.
HIGH_SIGNAL_TOKENS = {
    "python", "sql", "ai", "ml", "api", "apis", "rest", "cloud", "aws", "azure", "gcp", "docker",
    "kubernetes", "linux", "git", "github", "testing", "validation", "quality", "research", "audio",
    "speech", "nlp", "algorithms", "models", "training", "embedded", "tensorflow", "pytorch", "opencv",
    "pandas", "numpy", "matlab", "etl", "devops", "backend", "frontend", "fullstack", "architecture",
    "automation", "clients", "client", "consulting", "consultant", "stakeholder", "documentation",
}

ACTION_VERBS = {
    "built", "created", "developed", "designed", "implemented", "improved", "automated", "optimized",
    "managed", "led", "delivered", "analyzed", "reduced", "increased", "maintained", "supported",
    "launched", "integrated", "tested", "documented", "collaborated", "configured", "migrated",
    "validated", "evaluated", "trained", "processed", "modeled", "refined", "deployed",
}

GENERIC_WORDS = {
    "responsible", "worked", "helped", "various", "multiple", "tasks", "duties", "things", "stuff",
    "hardworking", "motivated", "passionate", "detail-oriented", "dynamic", "team player",
}

ATS_RISK_MARKERS = ["│", "┌", "┐", "└", "┘", "═", "•", "👉", "✅", "⭐", "🔥"]
PLACEHOLDER_PATTERNS = [
    r"\[[xX]\]",
    r"\bX\s*years?\b",
    r"\byour\s+name\b",
    r"\bcompany\s+name\b",
    r"\bemail@example\.com\b",
    r"\bphone\s+number\b",
]


@dataclass
class QualityReport:
    document_type: str
    score: int
    verdict: str
    contact_score: int
    keyword_score: int
    evidence_score: int
    ats_score: int
    risk_score: int
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    supported_keywords: list[str] = field(default_factory=list)
    unsupported_keywords: list[str] = field(default_factory=list)
    matched_supported_keywords: list[str] = field(default_factory=list)
    missing_supported_keywords: list[str] = field(default_factory=list)
    missing_unsupported_keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def analyze_document(
    document_text: str,
    job_description: str,
    profile: CandidateProfile,
    document_type: str = "Resume",
) -> QualityReport:
    """Run a strict, deterministic review of the generated career document.

    Step 12 makes the checker truth-aware: missing job signals that are not supported by the
    candidate evidence are reported as fit gaps, not as rewrite targets. This prevents the app
    from pretending that a regeneration can honestly add audio, embedded, DevOps, client work,
    or any other unsupported signal.
    """
    document_text = document_text or ""
    job_description = job_description or ""
    source_text = _candidate_source_text(profile)

    is_cover_letter = _is_cover_letter(document_type)

    contact_score, contact_warnings = _score_contact(document_text, profile)
    keywords = extract_job_keywords(job_description)
    supported_keywords, unsupported_keywords = split_keywords_by_candidate_evidence(keywords, profile)
    matched_keywords, missing_keywords = _match_keywords(document_text, keywords)

    matched_supported_keywords = [keyword for keyword in matched_keywords if keyword in supported_keywords]
    missing_supported_keywords = [keyword for keyword in missing_keywords if keyword in supported_keywords]
    missing_unsupported_keywords = [keyword for keyword in missing_keywords if keyword in unsupported_keywords]

    keyword_score = _score_supported_keywords(
        matched_supported_keywords=matched_supported_keywords,
        supported_keywords=supported_keywords,
        matched_all_keywords=matched_keywords,
        all_keywords=keywords,
    )
    if is_cover_letter:
        evidence_score, evidence_warnings, bullet_stats = _score_cover_letter_evidence(document_text)
    else:
        evidence_score, evidence_warnings, bullet_stats = _score_evidence(document_text)
    ats_score, ats_warnings = _score_ats(document_text, document_type=document_type)
    risk_score, risk_warnings = _score_risks(document_text, source_text, allow_first_person=is_cover_letter)

    fit_warnings = _build_fit_warnings(supported_keywords, unsupported_keywords, missing_supported_keywords)
    warnings = contact_warnings + evidence_warnings + ats_warnings + risk_warnings + fit_warnings
    recommendations = _build_recommendations(
        document_type=document_type,
        keyword_score=keyword_score,
        evidence_score=evidence_score,
        ats_score=ats_score,
        risk_score=risk_score,
        missing_supported_keywords=missing_supported_keywords,
        missing_unsupported_keywords=missing_unsupported_keywords,
        unsupported_keywords=unsupported_keywords,
        warnings=warnings,
    )

    score = contact_score + keyword_score + evidence_score + ats_score + risk_score
    score = max(0, min(100, score))
    verdict = _verdict(score, unsupported_keywords)

    stats = {
        "word_count": len(re.findall(r"\b\w+\b", document_text)),
        "bullet_count": bullet_stats["bullet_count"],
        "strong_bullet_count": bullet_stats["strong_bullet_count"],
        "paragraph_count": bullet_stats.get("paragraph_count", 0),
        "job_keyword_count": len(keywords),
        "matched_keyword_count": len(matched_keywords),
        "missing_keyword_count": len(missing_keywords),
        "supported_keyword_count": len(supported_keywords),
        "matched_supported_keyword_count": len(matched_supported_keywords),
        "missing_supported_keyword_count": len(missing_supported_keywords),
        "unsupported_keyword_count": len(unsupported_keywords),
        "missing_unsupported_keyword_count": len(missing_unsupported_keywords),
    }

    return QualityReport(
        document_type=document_type,
        score=score,
        verdict=verdict,
        contact_score=contact_score,
        keyword_score=keyword_score,
        evidence_score=evidence_score,
        ats_score=ats_score,
        risk_score=risk_score,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        supported_keywords=supported_keywords,
        unsupported_keywords=unsupported_keywords,
        matched_supported_keywords=matched_supported_keywords,
        missing_supported_keywords=missing_supported_keywords,
        missing_unsupported_keywords=missing_unsupported_keywords,
        warnings=warnings,
        recommendations=recommendations,
        stats=stats,
    )


def format_quality_report(report: QualityReport) -> str:
    matched = ", ".join(report.matched_keywords) if report.matched_keywords else "None detected"
    missing_supported = ", ".join(report.missing_supported_keywords[:20]) if report.missing_supported_keywords else "None detected"
    unsupported = ", ".join(report.unsupported_keywords[:20]) if report.unsupported_keywords else "None detected"
    matched_supported = ", ".join(report.matched_supported_keywords) if report.matched_supported_keywords else "None detected"
    warnings = "\n".join(f"- {item}" for item in report.warnings) if report.warnings else "- No major risks detected by the heuristic checker."
    recommendations = "\n".join(f"- {item}" for item in report.recommendations) if report.recommendations else "- Review manually before exporting or submitting."

    return f"""
# {report.document_type} Quality Check

## Overall score

**{report.score}/100**  
**Verdict:** {report.verdict}

## Score breakdown

| Area | Score |
|---|---:|
| Contact details | {report.contact_score}/15 |
| Truth-supported job match | {report.keyword_score}/35 |
| Evidence strength | {report.evidence_score}/20 |
| ATS formatting | {report.ats_score}/15 |
| Claim risk control | {report.risk_score}/15 |

## Document stats

| Metric | Value |
|---|---:|
| Word count | {report.stats.get("word_count", 0)} |
| Bullet count | {report.stats.get("bullet_count", 0)} |
| Strong bullet count | {report.stats.get("strong_bullet_count", 0)} |
| Paragraph count | {report.stats.get("paragraph_count", 0)} |
| Job signals detected | {report.stats.get("job_keyword_count", 0)} |
| Matched job signals | {report.stats.get("matched_keyword_count", 0)} |
| Supported job signals | {report.stats.get("supported_keyword_count", 0)} |
| Matched supported signals | {report.stats.get("matched_supported_keyword_count", 0)} |
| Missing supported signals | {report.stats.get("missing_supported_keyword_count", 0)} |
| Unsupported job signals | {report.stats.get("unsupported_keyword_count", 0)} |

## Matched supported job signals

{matched_supported}

## Missing supported job signals

{missing_supported}

## Unsupported job signals from the job description

{unsupported}

## All matched job signals

{matched}

## Warnings

{warnings}

## Recommended fixes

{recommendations}

## Hard rule

Do not add unsupported job signals just to increase a score. Improve the document by surfacing truthful evidence. Add new profile evidence only when it is real.
""".strip()


def extract_job_keywords(job_description: str, limit: int = 30) -> list[str]:
    """Extract high-signal job keywords without rewarding generic job-posting filler."""
    lower_text = _normalize_text(job_description or "")
    if not lower_text:
        return []

    phrase_hits: list[str] = []
    for phrase in sorted(SKILL_PHRASES, key=len, reverse=True):
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(_normalize_text(phrase)) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lower_text) and not _is_redundant_keyword(phrase, phrase_hits):
            phrase_hits.append(phrase)

    raw_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", lower_text)
    tokens = [token.strip(".,;:()[]{}").lower() for token in raw_tokens]
    filtered = [
        token for token in tokens
        if token not in STOPWORDS
        and token in HIGH_SIGNAL_TOKENS
        and len(token) > 2
    ]
    counts = Counter(filtered)

    token_hits: list[str] = []
    for token, _count in counts.most_common(60):
        if any(token in phrase.split() for phrase in phrase_hits):
            continue
        if not _is_redundant_keyword(token, phrase_hits + token_hits):
            token_hits.append(token)

    combined: list[str] = []
    for item in phrase_hits + token_hits:
        clean = item.strip().lower()
        if clean and clean not in combined:
            combined.append(clean)
        if len(combined) >= limit:
            break
    return combined


def split_keywords_by_candidate_evidence(keywords: list[str], profile: CandidateProfile) -> tuple[list[str], list[str]]:
    """Return job signals that are supported vs. not clearly supported by the candidate profile."""
    source_text = _candidate_source_text(profile)
    supported: list[str] = []
    unsupported: list[str] = []
    for keyword in keywords:
        if keyword_has_candidate_support(keyword, source_text):
            supported.append(keyword)
        else:
            unsupported.append(keyword)
    return supported, unsupported


def keyword_has_candidate_support(keyword: str, source_text: str) -> bool:
    source = _normalize_text(source_text or "")
    if not source:
        return False
    variants = _keyword_variants(keyword)
    variants.extend(_support_variants(keyword))
    return any(_contains_keyword(source, variant) for variant in variants if variant)


def build_truth_aware_signal_report(profile: CandidateProfile, job_description: str, limit: int = 24) -> str:
    """Build a compact support report for AI prompts."""
    keywords = extract_job_keywords(job_description, limit=limit)
    if not keywords:
        return "No high-signal job keywords were extracted. Rely on candidate evidence and the target title."

    supported, unsupported = split_keywords_by_candidate_evidence(keywords, profile)
    lines = ["Supported job signals to surface when relevant:"]
    lines.extend(f"- {signal}" for signal in supported[:limit])
    if not supported:
        lines.append("- None clearly supported yet. Add more candidate evidence before expecting a strong match.")
    lines.append("")
    lines.append("Unsupported job signals. Do not add unless the user adds truthful evidence:")
    lines.extend(f"- {signal}" for signal in unsupported[:limit])
    if not unsupported:
        lines.append("- None detected.")
    return "\n".join(lines)


def _match_keywords(document_text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    lower_doc = _normalize_text(document_text or "")
    matched = []
    missing = []
    for keyword in keywords:
        variants = _keyword_variants(keyword)
        if any(_contains_keyword(lower_doc, variant) for variant in variants):
            matched.append(keyword)
        else:
            missing.append(keyword)
    return matched, missing


def _normalize_text(text: str) -> str:
    text = text.lower().replace("state-of-the-art", "state of the art")
    text = text.replace("full-stack", "fullstack").replace("ci/cd", "cicd")
    return re.sub(r"\s+", " ", text).strip()


def _contains_keyword(text: str, keyword: str) -> bool:
    keyword = _normalize_text(keyword)
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword) + r"s?(?![a-zA-Z0-9])"
    return bool(re.search(pattern, text))


def _keyword_variants(keyword: str) -> list[str]:
    keyword = _normalize_text(keyword)
    variants = {keyword}
    if keyword in {"api", "apis"}:
        variants.update({"api", "apis", "rest api"})
    if keyword == "rest api":
        variants.update({"rest", "api", "apis", "rest api"})
    if keyword == "machine learning":
        variants.update({"ml", "machine learning"})
    if keyword == "deep learning":
        variants.update({"deep learning", "neural network", "neural networks", "deep learning models"})
    if keyword == "computer vision":
        variants.update({"computer vision", "image processing", "opencv", "microscopy"})
    if keyword == "audio processing":
        variants.update({"audio processing", "audio signal processing", "speech processing", "audio", "speech"})
    if keyword == "audio":
        variants.update({"audio", "speech", "audio processing", "speech processing"})
    if keyword == "signal processing":
        variants.update({"signal processing", "eeg", "audio processing", "time series"})
    if keyword == "model training":
        variants.update({"model training", "training models", "trained models", "training", "trained"})
    if keyword == "training":
        variants.update({"training", "trained", "model training", "training models"})
    if keyword == "models":
        variants.update({"model", "models", "machine learning model", "deep learning model", "neural network", "neural networks"})
    if keyword == "algorithms":
        variants.update({"algorithm", "algorithms", "computer vision algorithm", "deep learning", "machine learning"})
    if keyword == "research":
        variants.update({"research", "thesis", "study", "studied", "investigated", "evaluated", "experiment", "experiments"})
    if keyword in {"embedded", "embedded systems"}:
        variants.update({"embedded", "embedded systems", "edge", "device", "devices", "hardware", "sensor", "wearable"})
    if keyword == "quality":
        variants.update({"quality", "validation", "validated", "testing", "qa", "reliability"})
    if keyword == "full-stack":
        variants.update({"fullstack", "full stack", "full-stack"})
    if keyword == "ci/cd":
        variants.update({"ci/cd", "cicd", "continuous integration"})
    return list(variants)


def _support_variants(keyword: str) -> list[str]:
    """Broader variants used only to decide candidate evidence support, not exact output match."""
    keyword = _normalize_text(keyword)
    support_map = {
        "audio processing": ["audio processing", "audio signal processing", "speech processing", "speech", "audio"],
        "audio": ["audio", "speech", "audio processing", "speech processing"],
        "embedded": ["hardware", "device", "devices", "sensor", "wearable", "edge", "embedded"],
        "embedded systems": ["hardware", "device", "devices", "sensor", "wearable", "edge", "embedded"],
        "models": ["model", "models", "deep learning", "machine learning", "tensorflow", "pytorch", "neural"],
        "algorithms": ["algorithm", "algorithms", "deep learning", "machine learning", "computer vision", "image processing"],
        "research": ["research", "thesis", "master", "m.sc", "msc", "study", "studies", "evaluated", "investigated"],
        "quality": ["quality", "validation", "testing", "reliability", "validated"],
        "training": ["training", "trained", "tensorflow", "pytorch", "model"],
    }
    return support_map.get(keyword, [])


def _is_redundant_keyword(candidate: str, existing: list[str]) -> bool:
    candidate_norm = _normalize_text(candidate)
    for item in existing:
        item_norm = _normalize_text(item)
        if candidate_norm == item_norm:
            return True
        if candidate_norm in item_norm.split() and len(candidate_norm) <= 4:
            return True
        if item_norm in candidate_norm and len(item_norm) > 4:
            return True
    return False


def _score_contact(document_text: str, profile: CandidateProfile) -> tuple[int, list[str]]:
    score = 15
    warnings = []
    lower_doc = document_text.lower()

    if profile.name and profile.name.lower() not in lower_doc:
        score -= 4
        warnings.append("Candidate name is missing from the generated document.")
    if profile.email and profile.email.lower() not in lower_doc:
        score -= 4
        warnings.append("Candidate email is missing from the generated document.")
    if profile.phone and _digits(profile.phone) and _digits(profile.phone) not in _digits(document_text):
        score -= 4
        warnings.append("Candidate phone number is missing from the generated document.")
    if profile.links and not any(link_part.lower() in lower_doc for link_part in _important_link_parts(profile.links)):
        score -= 2
        warnings.append("Profile links may be missing from the generated document.")

    if not re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", document_text):
        score -= 3
        warnings.append("No email address pattern was detected in the output.")

    return max(0, score), warnings


def _score_supported_keywords(
    matched_supported_keywords: list[str],
    supported_keywords: list[str],
    matched_all_keywords: list[str],
    all_keywords: list[str],
) -> int:
    if not all_keywords:
        return 18
    if not supported_keywords:
        # The document cannot honestly match the role signals yet. Keep this neutral-low and warn elsewhere.
        return 18
    supported_ratio = len(matched_supported_keywords) / max(1, len(supported_keywords))
    all_ratio = len(matched_all_keywords) / max(1, len(all_keywords))
    # Most of the score rewards truthful supported alignment. A smaller part still reflects overall role fit.
    return min(35, round((supported_ratio * 27) + (all_ratio * 8)))


def _score_evidence(document_text: str) -> tuple[int, list[str], dict[str, int]]:
    bullets = [line.strip() for line in document_text.splitlines() if re.match(r"^\s*[-*]\s+", line)]
    warnings = []
    if not bullets:
        return 4, ["No bullet points were detected. CVs need scannable achievement bullets."], {
            "bullet_count": 0,
            "strong_bullet_count": 0,
        }

    strong_bullets = 0
    generic_bullets = 0
    for bullet in bullets:
        lower = bullet.lower()
        has_action = any(re.search(r"\b" + re.escape(verb) + r"\b", lower) for verb in ACTION_VERBS)
        has_specificity = bool(re.search(r"\b\d", bullet)) or any(skill in lower for skill in SKILL_PHRASES)
        has_result = any(word in lower for word in ["improved", "reduced", "increased", "delivered", "optimized", "automated", "saved", "launched", "validated", "reliability", "accuracy", "quality"])
        if has_action and (has_specificity or has_result):
            strong_bullets += 1
        if any(word in lower for word in GENERIC_WORDS):
            generic_bullets += 1

    ratio = strong_bullets / max(1, len(bullets))
    score = round(6 + ratio * 14)

    if len(bullets) < 6:
        score -= 3
        warnings.append("The document has too few bullets. Add more evidence from projects, experience, or education.")
    if generic_bullets >= max(2, len(bullets) // 3):
        score -= 3
        warnings.append("Too many bullets sound generic. Replace task descriptions with proof, tools, and outcomes.")
    if strong_bullets < max(2, len(bullets) // 3):
        warnings.append("Too few bullets combine action, specificity, and impact.")

    return max(0, min(20, score)), warnings, {
        "bullet_count": len(bullets),
        "strong_bullet_count": strong_bullets,
    }


def _score_cover_letter_evidence(document_text: str) -> tuple[int, list[str], dict[str, int]]:
    warnings = []
    word_count = len(re.findall(r"\b\w+\b", document_text or ""))
    blocks = [block.strip() for block in re.split(r"\n\s*\n", document_text or "") if block.strip()]
    paragraphs = [
        block for block in blocks
        if not block.startswith("#")
        and not re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", block)
        and not block.lower().startswith(("links:", "email:", "phone:", "location:"))
        and block.lower() not in {"dear hiring team,", "sincerely,"}
    ]

    score = 20
    if word_count < 180:
        score -= 5
        warnings.append("The covering letter is probably too short. Add one concrete evidence paragraph.")
    if word_count > 650:
        score -= 4
        warnings.append("The covering letter is too long. Cut repetition and keep it focused.")
    if len(paragraphs) < 3:
        score -= 4
        warnings.append("The covering letter needs a clearer letter flow: opening, evidence, role alignment, and closing.")
    if len(paragraphs) > 7:
        score -= 2
        warnings.append("The covering letter has too many paragraphs. Keep it tight and readable.")

    lower = (document_text or "").lower()
    if "dear" not in lower[:500]:
        score -= 2
        warnings.append("No greeting was detected. Add a simple greeting such as Dear Hiring Team.")
    if not any(closing in lower[-500:] for closing in ["sincerely", "kind regards", "best regards"]):
        score -= 2
        warnings.append("No professional closing was detected.")

    has_action = any(re.search(r"\b" + re.escape(verb) + r"\b", lower) for verb in ACTION_VERBS)
    has_specificity = any(skill in lower for skill in SKILL_PHRASES)
    has_result_or_purpose = any(word in lower for word in ["improved", "validated", "built", "developed", "designed", "reduced", "quality", "reliability", "accuracy", "automation", "training"])
    if not (has_action and (has_specificity or has_result_or_purpose)):
        score -= 5
        warnings.append("The covering letter needs stronger evidence. Add a concrete project, method, tool, or technical purpose.")

    return max(0, min(20, score)), warnings, {
        "bullet_count": len([line for line in (document_text or "").splitlines() if re.match(r"^\s*[-*]\s+", line)]),
        "strong_bullet_count": 0,
        "paragraph_count": len(paragraphs),
    }


def _score_ats(document_text: str, document_type: str = "Resume") -> tuple[int, list[str]]:
    score = 15
    warnings = []
    if any(marker in document_text for marker in ATS_RISK_MARKERS):
        score -= 5
        warnings.append("ATS formatting risk detected. Avoid icons, decorative bullets, tables, and box-drawing characters.")
    if "|" in document_text and re.search(r"\|\s*---", document_text):
        score -= 3
        warnings.append("Markdown table detected. Tables can parse badly in ATS systems.")
    if not re.search(r"^#{1,3}\s+", document_text, flags=re.MULTILINE):
        score -= 3
        warnings.append("No clear Markdown headings detected. Add simple section headings.")
    word_count = len(re.findall(r"\b\w+\b", document_text))
    if _is_cover_letter(document_type):
        if word_count < 180:
            score -= 4
            warnings.append("The covering letter is probably too short for a serious application.")
        if word_count > 650:
            score -= 3
            warnings.append("The covering letter may be too long. Keep it concise and focused.")
    else:
        if word_count < 250:
            score -= 4
            warnings.append("The document is probably too short for a serious application.")
        if word_count > 1400:
            score -= 3
            warnings.append("The document may be too long for a CV. Trim lower-value sections.")
    return max(0, score), warnings


def _score_risks(document_text: str, source_text: str, allow_first_person: bool = False) -> tuple[int, list[str]]:
    score = 15
    warnings = []
    lower_doc = document_text.lower()

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, lower_doc, flags=re.IGNORECASE):
            score -= 5
            warnings.append("Placeholder text detected. Remove [X], fake years, sample emails, or generic company placeholders.")
            break

    if "thinking..." in lower_doc or "done thinking" in lower_doc or "chain-of-thought" in lower_doc:
        score -= 8
        warnings.append("Model thinking text leaked into the output. Delete it and regenerate with stricter instructions.")

    unverified_numbers = _find_unverified_numbers(document_text, source_text)
    if unverified_numbers:
        score -= min(8, 2 + len(unverified_numbers))
        warnings.append(
            "Potentially unverified numbers or metrics detected: " + ", ".join(unverified_numbers[:8]) + ". Verify or remove them."
        )

    if not allow_first_person and re.search(r"\b(i|me|my)\b", lower_doc):
        score -= 2
        warnings.append("First-person wording detected. CV bullets usually work better without I, me, or my.")

    return max(0, score), warnings


def _find_unverified_numbers(document_text: str, source_text: str) -> list[str]:
    number_pattern = r"(?<!\w)(?:[$€£]\s*)?\d+(?:[.,]\d+)?\s*(?:%|percent|years?|yrs?|months?|weeks?|days?|k|m|million|billion)?(?!\w)"
    doc_numbers = re.findall(number_pattern, document_text, flags=re.IGNORECASE)
    source_lower = source_text.lower()
    unverified = []
    for number in doc_numbers:
        clean = " ".join(number.lower().split())
        digits_only = re.sub(r"\D", "", clean)
        if len(digits_only) >= 7:
            continue
        if clean and clean not in source_lower and digits_only and digits_only not in re.sub(r"\D", "", source_lower):
            if clean not in unverified:
                unverified.append(clean)
    return unverified


def _build_fit_warnings(
    supported_keywords: list[str],
    unsupported_keywords: list[str],
    missing_supported_keywords: list[str],
) -> list[str]:
    warnings: list[str] = []
    if unsupported_keywords and len(unsupported_keywords) >= max(3, len(supported_keywords)):
        warnings.append(
            "Many job signals are not supported by the candidate evidence. Regeneration cannot honestly fix this. Add real evidence or accept a weaker job fit."
        )
    if missing_supported_keywords:
        warnings.append(
            "Some supported job signals are still not visible enough in the document: " + ", ".join(missing_supported_keywords[:8]) + "."
        )
    return warnings


def _build_recommendations(
    document_type: str,
    keyword_score: int,
    evidence_score: int,
    ats_score: int,
    risk_score: int,
    missing_supported_keywords: list[str],
    missing_unsupported_keywords: list[str],
    unsupported_keywords: list[str],
    warnings: list[str],
) -> list[str]:
    recommendations = []
    if missing_supported_keywords:
        recommendations.append("Surface truthful evidence for supported job signals: " + ", ".join(missing_supported_keywords[:8]) + ".")
    elif keyword_score >= 25:
        recommendations.append("Do not chase unsupported keywords. Improve clarity, ordering, and evidence strength instead.")
    if missing_unsupported_keywords:
        recommendations.append("For unsupported job signals, add profile evidence only if it is true: " + ", ".join(missing_unsupported_keywords[:8]) + ".")
    if evidence_score < 15:
        if _is_cover_letter(document_type):
            recommendations.append("Strengthen the covering letter with one concrete evidence paragraph: relevant project or role + tool/method + reason it matters for this job.")
        else:
            recommendations.append("Rewrite weak bullets using this structure: action verb + tool or method + result or business purpose.")
    if ats_score < 12:
        recommendations.append("Simplify formatting before PDF export. Use plain headings, plain bullets, and no tables or icons.")
    if risk_score < 12:
        recommendations.append("Audit every number, date, tool, and achievement. Remove anything not supported by the candidate profile or source documents.")
    if _is_cover_letter(document_type):
        recommendations.append("Keep the covering letter concise: 3 to 5 paragraphs, clear role motivation, concrete evidence, and a professional closing.")
    else:
        recommendations.append("For a CV, keep relevant depth, but still remove empty sections and unsupported claims.")
    if not warnings:
        recommendations.append("Run one manual pass for accuracy, grammar, and role fit before exporting the PDF.")
    return recommendations


def _is_cover_letter(document_type: str) -> bool:
    normalized = (document_type or "").strip().lower().replace("_", "-")
    return normalized in {"covering letter", "cover letter", "cover-letter", "covering-letter"}


def _candidate_source_text(profile: CandidateProfile) -> str:
    return "\n".join(
        [
            profile.name,
            profile.email,
            profile.phone,
            profile.location,
            profile.title,
            profile.links,
            profile.summary,
            profile.studies,
            profile.professions,
            profile.projects,
            profile.skills,
            profile.languages,
            profile.general_cv,
            profile.general_cover_letter,
            profile.general_resume,
        ]
    )


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def _important_link_parts(links: str) -> list[str]:
    parts = re.split(r"[\s,;]+", links or "")
    useful = []
    for part in parts:
        stripped = part.strip().replace("https://", "").replace("http://", "").rstrip("/")
        if stripped:
            useful.append(stripped)
    return useful


def _verdict(score: int, unsupported_keywords: list[str] | None = None) -> str:
    unsupported_count = len(unsupported_keywords or [])
    if score >= 85:
        if unsupported_count:
            return "Document is strong, but the job fit has evidence gaps. Verify before submitting."
        return "Strong, but still verify every claim manually."
    if score >= 70:
        return "Usable after focused edits. Do not force unsupported job signals."
    if score >= 55:
        return "Needs serious revision before export."
    return "Not ready. Fix the basics before submitting."
