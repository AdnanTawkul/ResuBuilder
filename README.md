# Resume AI 2

Resume AI 2 is a local desktop application for tailoring resumes and CVs to a specific job description.

## Current features

- Application workspace save/load
- Candidate profile fields
- Job description input
- Existing CV and resume input
- Existing PDF resume/CV import
- PDF/text job description import
- Tailored CV generation
- Tailored resume generation
- Template selection
- PDF export
- Selectable PDF templates
- OpenAI provider support
- Ollama local AI provider support
- Resume quality checker
- AI quality review
- Regenerate with quality fixes
- AI review wait screen
- Quality-improvement wait screen
- Quality-improvement timeout guard
- Ollama non-thinking request mode for faster resume fixes
- Markdown code-fence cleanup for local model output
- Better job-signal extraction that ignores job-posting filler words
- Candidate evidence map added to generation and improvement prompts
- Stronger required Markdown structure for AI outputs
- Automatic contact-header repair when the model omits supplied contact details
- Lower-temperature Ollama settings for more consistent local output
- Truth-aware quality scoring that separates supported job signals from unsupported job-fit gaps
- Improved quality recommendations that stop chasing impossible keywords
- Improvement prompts now target only truthful supported gaps

## Run the app

```bash
python app.py
```

## PDF/text import workflow

The app can now import text from:

```text
.txt
.md
.pdf
```

You can use this for:

```text
- Job descriptions
- Existing CVs
- Existing resumes
```

PDF import is best-effort. It works on normal selectable-text PDFs. It does not perform OCR on scanned image-only PDFs yet.

## Application workspace workflow

Use the **Workspace** tab for each job application.

Recommended flow:

```text
1. Click New Application.
2. Enter application name, target company, and target role.
3. Fill or import candidate profile, job description, existing CV, or existing resume.
4. Generate the resume or CV.
5. Run Quality Check and AI Quality Review.
6. Improve with Quality Fixes if needed.
7. Save Application.
8. Export the final PDF.
```

Workspace files are saved as JSON under:

```text
data/applications/
```

A workspace stores:

```text
- Application metadata
- Candidate profile
- Job description
- Existing CV/resume input
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
2. Import an existing PDF resume into the Existing CV / Resume tab.
3. Import or paste a job description.
4. Generate a tailored resume.
5. Run Quality Check.
6. Run AI Quality Review.
7. Click Improve with Quality Fixes.
8. Save the application workspace.
9. Close and reopen the app.
10. Load the saved application workspace.
11. Confirm imported text, generated output, and quality report restore correctly.
12. Export PDF only after manual verification.

## Git workflow

Use GitHub Desktop. Keep each major feature on its own branch until tested.

Recommended branch:

```text
feature/pdf-import
```

Recommended commit for this update:

```text
Add PDF import for existing resumes and CVs
```
