# Resume AI 2

Resume AI 2 is a local desktop application for tailoring CVs and covering letters to a specific job description.

## Current features

- Application workspace save/load
- Candidate profile fields
- Structured evidence builder for projects, jobs, tools, outcomes, proof, and job signals
- Job description input
- AI-powered Job Fit Analyzer using Ollama before generation
- App settings persistence for AI, template, PDF, and folder defaults
- Sidebar workflow GUI with step status, skip options, and simplified navigation
- Modern visual theme with cleaner spacing, updated typography, highlighted workflow steps, and styled text areas
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

Install or update dependencies first:

```bash
pip install -r requirements.txt
```

Then run:

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

Use the **Workspace** step for each job application.

Recommended flow:

```text
1. Click New Application.
2. Enter application name, target company, and target role.
3. Fill or import candidate profile, job description, existing CV, or existing covering letter.
4. Add structured evidence blocks for the strongest projects, jobs, tools, outcomes, and proof.
5. Run Job Fit Analyzer to create a truthful generation strategy.
6. Generate the CV or covering letter.
7. Run Quality Check and AI Quality Review.
8. Improve with Quality Fixes if needed.
9. Save Application.
10. Export the full application package.
```

Workspace files are saved as JSON under:

```text
data/applications/
```

Use **Export Application Package** in the Export step after both final documents are generated. It creates a folder under `exports/` or your configured export directory with:

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
- Structured evidence blocks
- Job description
- Existing CV/covering-letter input
- Selected templates
- Selected AI provider settings, excluding the session OpenAI API key
- Generated output
- Quality report
- AI review
- Job fit analysis and generation strategy
```

Do not commit private application workspace JSON files to GitHub unless they contain fake/demo data.

## Job Fit Analyzer workflow

Use the **Job Fit** step before generating documents. It uses Ollama locally to compare the job description against the profile, existing CV/covering letter, and structured evidence.

It produces:

```text
- Fit score
- Strong alignment
- Weak alignment
- Unsupported or risky claims
- Recommended CV strategy
- Recommended covering-letter strategy
- Evidence gaps to fill
- Generation instructions
```

The analysis is automatically included in the next CV and covering-letter generation prompt. This prevents the app from chasing unsupported keywords or producing fake alignment.

## Sidebar workflow

The app now uses a sidebar workflow instead of crowded top tabs. The workflow is:

```text
Workspace
Profile
Evidence
Job Description
Job Fit
Generate
Review
Export
Settings
```

Each step shows a status marker:

```text
✓ complete
○ not started
⚠ needs attention
↷ skipped
```

Required steps cannot be skipped. Optional steps can be skipped, but the app warns when skipping may reduce output quality. The top navigation uses **Back**, **Skip & Continue**, and **Complete & Continue** so there is no redundant generic Next action. The goal is workflow clarity: the user should always know what to do next.

## Modern GUI update

The app now has a cleaner modern visual shell while keeping the existing sidebar workflow and app logic stable. The update improves:

```text
- Sidebar highlighting for the current step
- Softer background and card-like surfaces
- Cleaner button and input styling
- Larger default window size
- More readable text areas
- Consistent Segoe UI typography
- Better spacing around the workflow content
```

This is an incremental modernization, not a risky full rewrite. The app imports CustomTkinter when available and still falls back safely if the dependency is missing.

## App settings persistence

The app now saves non-secret preferences locally under:

```text
data/settings.json
```

Saved settings include:

```text
- AI provider
- OpenAI model name, but not the API key
- Ollama base URL
- Ollama model
- Timeout seconds
- Generation mode
- Default document template
- Default PDF template
- Default PDF page size
- Last workspace folder
- Last export folder
```

The app saves settings on close and also has **Save App Settings** and **Reset App Settings** buttons in the Settings step. OpenAI session API keys are deliberately not saved.

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
2. Import an existing PDF CV or covering letter in the Profile step.
3. Import or paste a job description.
4. Add structured evidence blocks for your strongest relevant proof.
5. Run Job Fit Analyzer.
6. Confirm the fit strategy is truthful and not chasing unsupported keywords.
7. Generate a tailored CV.
8. Generate a tailored covering letter.
9. Run Quality Check on both document types.
10. Run AI Quality Review.
11. Click Improve with Quality Fixes.
12. Save the application workspace.
13. Close and reopen the app.
14. Load the saved application workspace.
15. Confirm structured evidence, job fit analysis, imported text, generated output, and quality report restore correctly.
16. Click Export Application Package only after manual verification.
17. Confirm the export folder contains the CV PDF, covering letter PDF, quality report, and summary JSON.
18. Close and reopen the app, then confirm your AI provider, Ollama model, timeout, PDF template, and page size are remembered.

## Git workflow

Use GitHub Desktop. Keep each major feature on its own branch until tested.

Recommended branch:

```text
feature/gui-visual-polish
```

Recommended commit for this update:

```text
Improve GUI visual layout and usability
```


## Sidebar prompt preview fix

Prompt preview now opens in a dedicated preview window instead of writing to the old Output tab area. This prevents prompt previews from overwriting generated CV or covering letter content and matches the sidebar workflow.

## Step 20 navigation cleanup

- Removed the redundant **Next** button from the sidebar workflow header.
- Renamed **Skip This Step** to **Skip & Continue**.
- Renamed **Mark Step Complete** to **Complete & Continue**.
- Completing a step now moves directly to the next step.


## Step 21 modern GUI polish

- Added a modern visual theme layer.
- Increased default app size for a less cramped workflow.
- Highlighted the active sidebar step.
- Styled complete and warning workflow states.
- Improved text area readability.
- Added CustomTkinter as an optional modern UI dependency while preserving the current Tkinter/ttk implementation.

- Fixed the Export step action bar so buttons wrap into two rows and no longer get cropped at the default window width.
