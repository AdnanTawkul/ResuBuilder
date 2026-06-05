from __future__ import annotations

from pathlib import Path


SUPPORTED_IMPORT_EXTENSIONS = {".txt", ".md", ".pdf"}


def load_document_text(path: str | Path) -> str:
    """Load plain text from a supported document file.

    Supported formats:
    - .txt
    - .md
    - .pdf

    PDF import is best-effort. Scanned image-only PDFs require OCR, which this app
    does not perform yet.
    """
    source_path = Path(path)
    suffix = source_path.suffix.lower()

    if suffix not in SUPPORTED_IMPORT_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}. Use .txt, .md, or .pdf.")

    if suffix in {".txt", ".md"}:
        return _load_text_file(source_path)

    if suffix == ".pdf":
        return _load_pdf_file(source_path)

    raise ValueError(f"Unsupported file type: {suffix}")


def _load_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").strip()


def _load_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF import requires the pypdf package. Run: pip install -r requirements.txt"
        ) from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = _clean_imported_text(page_text)
        if page_text:
            pages.append(f"[Page {page_number}]\n{page_text}")

    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError(
            "No selectable text was found in this PDF. It may be scanned/image-only. OCR import is not supported yet."
        )
    return text


def _clean_imported_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    lines = [line.strip() for line in cleaned.splitlines()]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        compact_lines.append(line)
        previous_blank = is_blank
    return "\n".join(compact_lines).strip()
