# Resume AI 2

Resume AI 2 is a Python desktop app that helps tailor CVs and resumes to a specific job description.

## Current features

- Personal information tab.
- Job description tab.
- Existing CV and resume input tab.
- Template selection tab.
- Generate tailored CV button.
- Generate tailored resume button.
- Markdown output saved to the `exports` folder.
- Local candidate profile saved to the `data` folder.
- Optional OpenAI integration when `OPENAI_API_KEY` is available.

## Project structure

```text
resume_ai_2/
├── app.py
├── requirements.txt
├── README.md
├── docs/
│   └── ROADMAP.md
├── exports/
└── src/
    └── resume_ai/
        ├── __init__.py
        ├── ai_service.py
        ├── gui.py
        ├── models.py
        ├── storage.py
        └── templates.py
```

## Run locally in PyCharm

1. Open PyCharm.
2. Click **Open**.
3. Select the `resume_ai_2` folder.
4. Open `app.py`.
5. Click the green run button.

## Optional AI setup

The app works without an API key by creating a local draft. To use OpenAI:

1. Install requirements:

```bash
pip install -r requirements.txt
```

2. Set your API key as an environment variable.

Windows PowerShell:

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

macOS or Linux:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

3. Restart PyCharm after setting the key.

## GitHub Desktop workflow

1. Open GitHub Desktop.
2. Click **File > Add Local Repository**.
3. Choose the `resume_ai_2` folder.
4. If GitHub Desktop says it is not a repository, click **create a repository**.
5. Write a commit summary such as `Create initial GUI app`.
6. Click **Commit to main**.
7. Click **Publish repository**.

## Recommended commit habit

Make one small commit after each working feature:

- `Create initial project structure`
- `Add GUI tabs`
- `Add profile saving`
- `Add document generation service`
- `Add template selector`
- `Add AI integration`
- `Add DOCX export`

Do not make one huge commit after days of work. That is how messy projects become impossible to review.
