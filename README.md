# Resume AI 2

Resume AI 2 is a Python desktop app that helps tailor CVs and resumes to a specific job description.

## Current features

- Personal information tab.
- Job description tab.
- Existing CV and resume input tab.
- Template selection tab.
- AI Settings tab.
- Generate tailored CV button.
- Generate tailored resume button.
- Markdown output saved to the `exports` folder.
- PDF export from the generated output.
- Selectable PDF templates:
  - ATS Friendly
  - Professional
  - Modern
  - Academic CV
- A4 and Letter PDF page sizes.
- Local candidate profile saved to the `data` folder.
- OpenAI integration through the Responses API when an API key is available.
- Session API key entry for temporary testing.
- AI connection test button.
- Prompt preview button.
- Model selector.
- Generation mode selector:
  - Conservative
  - Balanced
  - Aggressive

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
        ├── pdf_exporter.py
        ├── pdf_templates.py
        ├── storage.py
        └── templates.py
```

## Install dependencies

In PyCharm, open the Terminal at the bottom of the window and run:

```bash
pip install -r requirements.txt
```

Run this after pulling or copying project updates that change `requirements.txt`.

## Run locally in PyCharm

1. Open PyCharm.
2. Click **Open**.
3. Select the `resume_ai_2` folder.
4. Open `app.py`.
5. Click the green run button.

## AI setup

The app uses OpenAI only when an API key is available. Without a key, it creates a local draft so the app still works.

### Recommended setup on Windows PowerShell

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

Then close and reopen PyCharm.

### Temporary setup inside the app

1. Open the **AI Settings** tab.
2. Paste your API key into **Session API key**.
3. Choose a model.
4. Choose a generation mode.
5. Click **Test AI Connection**.
6. Generate a tailored CV or resume.

Session API keys are not saved in the candidate profile.

## Export a PDF

1. Fill in the personal information.
2. Paste a job description.
3. Choose a writing template in the **Templates** tab.
4. Configure AI in the **AI Settings** tab.
5. Click **Generate Tailored CV** or **Generate Tailored Resume**.
6. Open the **Output** tab.
7. Choose a PDF template and page size.
8. Click **Export Output as PDF**.

## GitHub Desktop workflow

1. Open GitHub Desktop.
2. Make sure the current repository is `ResuBuilder` or your actual project folder.
3. Review changed files before committing.
4. Write a clear commit summary.
5. Click **Commit to main**.
6. Click **Push origin**.

Good commit examples:

- `Create initial GUI app`
- `Add PDF export`
- `Add selectable PDF templates`
- `Add OpenAI generation settings`

Do not make one huge commit after days of work. Small commits are easier to review, easier to debug, and more professional on GitHub.
