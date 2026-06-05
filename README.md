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
- Fixed AI review wait screen so stale heuristic output is not mistaken for a finished AI review

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
Timeout: 120
```

## Git workflow

Use GitHub Desktop. Keep experimental AI work on a feature branch until tested.

Recommended branch:

```text
feature/local-ai-provider
```

Recommended commit for this update:

```text
Fix AI review wait screen
```
