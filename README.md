# Resume AI 2

Resume AI 2 is a local desktop application for tailoring resumes and CVs to a specific job description.

## Current features

- Candidate profile fields
- Job description input
- Existing CV and resume input
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

1. Generate a tailored resume.
2. Run Quality Check.
3. Run AI Quality Review.
4. Click Improve with Quality Fixes.
5. Confirm the Output tab shows the running screen.
6. Wait for the improved document to replace the running screen.
7. Run Quality Check again.
8. Export PDF only after manual verification.

## Git workflow

Use GitHub Desktop. Keep experimental AI work on a feature branch until tested.

Recommended branch:

```text
feature/local-ai-provider
```

Recommended commit for this update:

```text
Add truth-aware quality scoring
```


## Why regeneration may not raise the score

If the job asks for audio processing, embedded systems, DevOps, clients, or research, but the candidate profile does not contain truthful evidence for those signals, the app must not invent them. In that case, the correct fix is to add real evidence to the Personal Info fields, not to regenerate forever.

Step 12 separates:

```text
Supported job signals = safe to surface in the resume
Unsupported job signals = job-fit gaps; do not add unless truthful
```
