# Resume AI 2 Roadmap

## Done

- Initial desktop GUI.
- Personal information form.
- Job description input.
- Existing CV and resume input.
- Template selection.
- Markdown output.
- PDF export.
- Selectable PDF templates.
- OpenAI generation settings.
- Prompt preview.
- Background AI generation.
- Ollama Local AI provider.

## Next priorities

### 1. Resume quality checker

Add a review panel that scores the generated resume or CV before export.

Target checks:

- Missing contact details.
- Weak summary.
- Too few role-specific keywords.
- Too many generic bullets.
- Possible fake metrics.
- Missing projects or experience evidence.
- ATS formatting risks.

### 2. Job keyword match score

Compare the job description against the generated document and show:

- Matched keywords.
- Missing keywords.
- Overused keywords.
- Suggested truthful improvements.

### 3. Better local AI controls

Add:

- Model speed/quality labels.
- Local generation timer.
- Token or prompt-size estimate.
- Warning when source documents are too long.

### 4. File import

Later, add PDF and DOCX import for existing resumes and CVs.

Do not build this before the quality checker. Import is useful, but poor generated output is the bigger product risk.
