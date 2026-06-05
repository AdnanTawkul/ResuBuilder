# Resume AI 2

Resume AI 2 is a local desktop application for tailoring CVs and covering letters to a specific job description.

## Current features

- Application workspace save/load
- Candidate profile fields
- Job description input
- Existing CV and covering letter input
- Existing PDF CV/covering-letter import
- PDF/text job description import
- Tailored CV generation
- Tailored covering letter generation
- Template selection
- PDF export
- Selectable PDF templates
- OpenAI provider support
- Ollama local AI provider support
- Career document quality checker
- AI quality review
- Regenerate with quality fixes
- AI review wait screen
- Quality-improvement wait screen
- Quality-improvement timeout guard
- Ollama non-thinking request mode for faster fixes
- Markdown code-fence cleanup for local model output
- Better job-signal extraction that ignores job-posting filler words
- Candidate evidence map added to generation and improvement prompts
- Stronger required Markdown structure for AI outputs
- Automatic contact-header repair when the model omits supplied contact details
- Lower-temperature Ollama settings for more consistent local output
- Truth-aware quality scoring that separates supported job signals from unsupported job-fit gaps
- Covering-letter-specific generation, review, and quality-check logic
- One-click application package export
- Separate stored generated CV and covering letter outputs
- Package export with final PDFs, Markdown sources, quality report, and summary JSON

## Run the app

```bash
python app.py
```

## PDF/text import workflow

The app can import text from:

```text
.txt
.md
.pdf
```

You can use this for:

```text
- Job descriptions
- Existing CVs
- Existing covering letters
```

PDF import is best-effort. It works on normal selectable-text PDFs. It does not perform OCR on scanned image-only PDFs yet.

## Application workspace workflow

Use the **Workspace** tab for each job application.

Recommended flow:

```text
1. Click New Application.
2. Enter application name, target company, and target role.
3. Fill or import candidate profile, job description, existing CV, or existing covering letter.
4. Generate the CV or covering letter.
5. Run Quality Check and AI Quality Review.
6. Improve with Quality Fixes if needed.
7. Save Application.
8. Export the full application package.
```

Workspace files are saved as JSON under:

```text
data/applications/
```

Use **Export Application Package** in the Output tab after both final documents are generated. It creates a folder under `exports/` or your configured export directory with:

```text
- Final CV PDF
- Final covering letter PDF
- CV Markdown source
- Covering letter Markdown source
- Quality report Markdown
- Application summary JSON
```

A workspace stores:

```text
- Application metadata
- Candidate profile
- Job description
- Existing CV/covering-letter input
- Selected templates
- Selected AI provider settings, excluding the session OpenAI API key
- Generated output
- Quality report
- AI review
```

Do not commit private application workspace JSON files to GitHub unless they contain fake/demo data.

## Local AI setup

Install Ollama, then run:

```powershell
ollama pull qwen3:14b
ollama run qwen3:14b
```

In the app, use:

```text
Provider: Ollama Local
Base URL: http://localhost:11434
Model: qwen3:14b
Timeout: 180
```

If quality improvement is too slow, use:

```text
Model: qwen3:8b
Timeout: 240
```

## Testing checklist

1. Create a new application workspace.
2. Import an existing PDF CV or covering letter into the Existing CV / Covering Letter tab.
3. Import or paste a job description.
4. Generate a tailored CV.
5. Generate a tailored covering letter.
6. Run Quality Check on both document types.
7. Run AI Quality Review.
8. Click Improve with Quality Fixes.
9. Save the application workspace.
10. Close and reopen the app.
11. Load the saved application workspace.
12. Confirm imported text, generated output, and quality report restore correctly.
13. Click Export Application Package only after manual verification.
14. Confirm the export folder contains the CV PDF, covering letter PDF, quality report, and summary JSON.

## Git workflow

Use GitHub Desktop. Keep each major feature on its own branch until tested.

Recommended branch:

```text
feature/application-package-export
```

Recommended commit for this update:

```text
Add application package export
```
