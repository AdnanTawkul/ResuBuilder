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
    "need", "needs", "looking", "seeking", "must", "plus", "using", "based", "within",
}

SKILL_PHRASES = [
    "python", "sql", "excel", "power bi", "tableau", "machine learning", "data analysis", "data science",
    "statistics", "automation", "api", "apis", "rest", "fastapi", "flask", "django", "tkinter", "pyqt",
    "desktop applications", "gui", "git", "github", "docker", "kubernetes", "aws", "azure", "gcp",
    "linux", "windows", "testing", "unit testing", "pytest", "agile", "scrum", "stakeholder",
    "project management", "leadership", "communication", "customer", "sales", "marketing", "research",
    "finance", "reporting", "quality", "security", "devops", "ci/cd", "etl", "pandas", "numpy",
]

ACTION_VERBS = {
    "built", "created", "developed", "designed", "implemented", "improved", "automated", "optimized",
    "managed", "led", "delivered", "analyzed", "reduced", "increased", "maintained", "supported",
    "launched", "integrated", "tested", "documented", "collaborated", "configured", "migrated",
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
    score: int
    verdict: str
    contact_score: int
    keyword_score: int
    evidence_score: int
    ats_score: int
    risk_score: int
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def analyze_document(
    document_text: str,
    job_description: str,
    profile: CandidateProfile,
    document_type: str = "Resume",
) -> QualityReport:
    """Run a strict, deterministic review of the generated career document."""
    document_text = document_text or ""
    job_description = job_description or ""
    source_text = _candidate_source_text(profile)

    contact_score, contact_warnings = _score_contact(document_text, profile)
    keywords = extract_job_keywords(job_description)
    matched_keywords, missing_keywords = _match_keywords(document_text, keywords)
    keyword_score = _score_keywords(matched_keywords, keywords)
    evidence_score, evidence_warnings, bullet_stats = _score_evidence(document_text)
    ats_score, ats_warnings = _score_ats(document_text)
    risk_score, risk_warnings = _score_risks(document_text, source_text)

    warnings = contact_warnings + evidence_warnings + ats_warnings + risk_warnings
    recommendations = _build_recommendations(
        document_type=document_type,
        keyword_score=keyword_score,
        evidence_score=evidence_score,
        ats_score=ats_score,
        risk_score=risk_score,
        missing_keywords=missing_keywords,
        warnings=warnings,
    )

    score = contact_score + keyword_score + evidence_score + ats_score + risk_score
    score = max(0, min(100, score))
    verdict = _verdict(score)

    stats = {
        "word_count": len(re.findall(r"\b\w+\b", document_text)),
        "bullet_count": bullet_stats["bullet_count"],
        "strong_bullet_count": bullet_stats["strong_bullet_count"],
        "job_keyword_count": len(keywords),
        "matched_keyword_count": len(matched_keywords),
        "missing_keyword_count": len(missing_keywords),
    }

    return QualityReport(
        score=score,
        verdict=verdict,
        contact_score=contact_score,
        keyword_score=keyword_score,
        evidence_score=evidence_score,
        ats_score=ats_score,
        risk_score=risk_score,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        warnings=warnings,
        recommendations=recommendations,
        stats=stats,
    )


def format_quality_report(report: QualityReport) -> str:
    matched = ", ".join(report.matched_keywords) if report.matched_keywords else "None detected"
    missing = ", ".join(report.missing_keywords[:20]) if report.missing_keywords else "None detected"
    warnings = "\n".join(f"- {item}" for item in report.warnings) if report.warnings else "- No major risks detected by the heuristic checker."
    recommendations = "\n".join(f"- {item}" for item in report.recommendations) if report.recommendations else "- Review manually before exporting or submitting."

    return f"""
# Resume Quality Check

## Overall score

**{report.score}/100**  
**Verdict:** {report.verdict}

## Score breakdown

| Area | Score |
|---|---:|
| Contact details | {report.contact_score}/15 |
| Job keyword match | {report.keyword_score}/35 |
| Evidence and bullet strength | {report.evidence_score}/20 |
| ATS formatting | {report.ats_score}/15 |
| Claim risk control | {report.risk_score}/15 |

## Document stats

| Metric | Value |
|---|---:|
| Word count | {report.stats.get("word_count", 0)} |
| Bullet count | {report.stats.get("bullet_count", 0)} |
| Strong bullet count | {report.stats.get("strong_bullet_count", 0)} |
| Job keywords detected | {report.stats.get("job_keyword_count", 0)} |
| Matched keywords | {report.stats.get("matched_keyword_count", 0)} |
| Missing keywords | {report.stats.get("missing_keyword_count", 0)} |

## Matched keywords

{matched}

## Missing keywords

{missing}

## Warnings

{warnings}

## Recommended fixes

{recommendations}

## Hard rule

Do not add missing keywords unless they are truthful for the candidate. A resume that matches the job by lying is worse than a resume that misses a few keywords.
""".strip()


def extract_job_keywords(job_description: str, limit: int = 30) -> list[str]:
    lower_text = (job_description or "").lower()
    phrase_hits = [phrase for phrase in SKILL_PHRASES if phrase in lower_text]

    raw_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{2,}", lower_text)
    tokens = [token.strip(".,;:()[]{}") for token in raw_tokens]
    filtered = [token for token in tokens if token not in STOPWORDS and len(token) > 2]
    counts = Counter(filtered)

    token_hits = []
    for token, _count in counts.most_common(60):
        if token in phrase_hits:
            continue
        if any(token in phrase.split() for phrase in phrase_hits):
            continue
        token_hits.append(token)

    combined = []
    for item in phrase_hits + token_hits:
        clean = item.strip().lower()
        if clean and clean not in combined:
            combined.append(clean)
        if len(combined) >= limit:
            break
    return combined


def _match_keywords(document_text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    lower_doc = (document_text or "").lower()
    matched = []
    missing = []
    for keyword in keywords:
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword.lower()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lower_doc):
            matched.append(keyword)
        else:
            missing.append(keyword)
    return matched, missing


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


def _score_keywords(matched_keywords: list[str], keywords: list[str]) -> int:
    if not keywords:
        return 18
    ratio = len(matched_keywords) / max(1, len(keywords))
    return min(35, round(ratio * 35))


def _score_evidence(document_text: str) -> tuple[int, list[str], dict[str, int]]:
    bullets = [line.strip() for line in document_text.splitlines() if re.match(r"^\s*[-*]\s+", line)]
    warnings = []
    if not bullets:
        return 4, ["No bullet points were detected. Resumes need scannable achievement bullets."], {
            "bullet_count": 0,
            "strong_bullet_count": 0,
        }

    strong_bullets = 0
    generic_bullets = 0
    for bullet in bullets:
        lower = bullet.lower()
        has_action = any(re.search(r"\b" + re.escape(verb) + r"\b", lower) for verb in ACTION_VERBS)
        has_specificity = bool(re.search(r"\b\d", bullet)) or any(skill in lower for skill in SKILL_PHRASES)
        has_result = any(word in lower for word in ["improved", "reduced", "increased", "delivered", "optimized", "automated", "saved", "launched"])
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


def _score_ats(document_text: str) -> tuple[int, list[str]]:
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
    if word_count < 250:
        score -= 4
        warnings.append("The document is probably too short for a serious application.")
    if word_count > 1400:
        score -= 3
        warnings.append("The document may be too long for a resume. Consider moving detail to a CV or trimming lower-value sections.")
    return max(0, score), warnings


def _score_risks(document_text: str, source_text: str) -> tuple[int, list[str]]:
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

    if re.search(r"\b(i|me|my)\b", lower_doc):
        score -= 2
        warnings.append("First-person wording detected. Resume bullets usually work better without I, me, or my.")

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


def _build_recommendations(
    document_type: str,
    keyword_score: int,
    evidence_score: int,
    ats_score: int,
    risk_score: int,
    missing_keywords: list[str],
    warnings: list[str],
) -> list[str]:
    recommendations = []
    if keyword_score < 25 and missing_keywords:
        recommendations.append("Add truthful evidence for the highest-value missing keywords: " + ", ".join(missing_keywords[:8]) + ".")
    if evidence_score < 15:
        recommendations.append("Rewrite weak bullets using this structure: action verb + tool or method + result or business purpose.")
    if ats_score < 12:
        recommendations.append("Simplify formatting before PDF export. Use plain headings, plain bullets, and no tables or icons.")
    if risk_score < 12:
        recommendations.append("Audit every number, date, tool, and achievement. Remove anything not supported by the candidate profile or source documents.")
    if document_type.lower() == "resume":
        recommendations.append("Keep the resume tight. If a section does not help the target job, cut it.")
    else:
        recommendations.append("For a CV, keep relevant depth, but still remove empty sections and unsupported claims.")
    if not warnings:
        recommendations.append("Run one manual pass for accuracy, grammar, and role fit before exporting the PDF.")
    return recommendations


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


def _verdict(score: int) -> str:
    if score >= 85:
        return "Strong, but still verify every claim manually."
    if score >= 70:
        return "Usable after focused edits."
    if score >= 55:
        return "Needs serious revision before export."
    return "Not ready. Fix the basics before submitting."
