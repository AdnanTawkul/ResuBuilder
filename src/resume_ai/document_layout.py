from __future__ import annotations

from dataclasses import dataclass
import re


PAGE_BREAK_MARKER = "<!-- RESUBUILDER_PAGE_BREAK -->"


def is_page_break_marker(line: str) -> bool:
    stripped = line.strip()
    return stripped in {PAGE_BREAK_MARKER, "[[PAGE_BREAK]]", "<!-- PAGE_BREAK -->"}


@dataclass(frozen=True)
class MarkdownSection:
    heading: str
    text: str


_H2_RE = re.compile(r"^##\s+(.+?)\s*$")


def _clean_heading(raw: str) -> str:
    return raw.strip().strip("#").strip()


def extract_markdown_sections(content: str) -> list[MarkdownSection]:
    """Return level-2 Markdown sections from a generated CV-like document.

    The prefix before the first level-2 heading is intentionally excluded because it
    usually contains the candidate name/contact header and should stay at the top.
    """
    lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    sections: list[MarkdownSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = _H2_RE.match(line.strip())
        if match:
            if current_heading is not None:
                sections.append(MarkdownSection(current_heading, "\n".join(current_lines).rstrip()))
            current_heading = _clean_heading(match.group(1))
            current_lines = [line]
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append(MarkdownSection(current_heading, "\n".join(current_lines).rstrip()))

    return sections


def _split_prefix_and_sections(content: str) -> tuple[str, list[MarkdownSection]]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    prefix_lines: list[str] = []
    section_lines: list[str] = []
    seen_h2 = False

    for line in lines:
        if _H2_RE.match(line.strip()):
            seen_h2 = True
        if seen_h2:
            section_lines.append(line)
        else:
            prefix_lines.append(line)

    return "\n".join(prefix_lines).rstrip(), extract_markdown_sections("\n".join(section_lines))


def reorder_markdown_sections(content: str, desired_order: list[str]) -> str:
    """Reorder level-2 sections while preserving the candidate header.

    Unknown sections remain in their original relative order after the requested
    sections. Duplicate headings are preserved by placing the first matching section
    for each desired heading, then appending remaining sections.
    """
    prefix, sections = _split_prefix_and_sections(content)
    if not sections:
        return content

    remaining = sections[:]
    ordered: list[MarkdownSection] = []

    for heading in desired_order:
        for index, section in enumerate(remaining):
            if section.heading == heading:
                ordered.append(section)
                remaining.pop(index)
                break

    ordered.extend(remaining)

    parts: list[str] = []
    if prefix.strip():
        parts.append(prefix.strip())
    parts.extend(section.text.strip() for section in ordered if section.text.strip())
    return "\n\n".join(parts).strip() + "\n"



def insert_page_break_after_section(content: str, heading: str) -> str:
    """Insert a manual PDF page break marker after a level-2 section.

    The marker is stored in the Markdown source and interpreted by the PDF
    exporter. It is intentionally plain text/HTML-comment style so saved
    workspaces remain portable and easy to inspect.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines or not heading.strip():
        return content

    target = _clean_heading(heading)
    section_start: int | None = None
    for index, line in enumerate(lines):
        match = _H2_RE.match(line.strip())
        if match and _clean_heading(match.group(1)) == target:
            section_start = index
            break

    if section_start is None:
        return content

    insert_at = len(lines)
    for index in range(section_start + 1, len(lines)):
        if _H2_RE.match(lines[index].strip()):
            insert_at = index
            break

    # Do not insert duplicate page breaks after the same section.
    previous_index = insert_at - 1
    while previous_index >= 0 and not lines[previous_index].strip():
        previous_index -= 1
    if previous_index >= 0 and is_page_break_marker(lines[previous_index]):
        return normalized.rstrip() + "\n"

    marker_block = ["", PAGE_BREAK_MARKER, ""]
    updated = lines[:insert_at] + marker_block + lines[insert_at:]
    return "\n".join(updated).rstrip() + "\n"


def remove_page_break_markers(content: str) -> str:
    """Remove manual page break markers from a generated document."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    kept = [line for line in normalized.splitlines() if not is_page_break_marker(line)]
    # Collapse excessive blank lines left by marker removal.
    text = "\n".join(kept)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.rstrip() + "\n" if text.strip() else ""
