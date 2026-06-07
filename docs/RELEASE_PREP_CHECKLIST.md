# Release Preparation Checklist

Use this before tagging a GitHub release.

## Source app

- `python app.py` opens ResuBuilder Qt app
- `python app_legacy.py` opens the legacy GUI
- Settings persist after restart
- Profile import/export works
- Workspace save/load works
- Evidence restores correctly
- Job data restores correctly
- Job fit analysis restores correctly
- Quality report restores correctly

## Documents

- CV PDF export works
- Covering letter PDF export works
- Application package export creates both PDFs and Markdown files
- Export folder naming is readable
- Private `data/` files are ignored by Git

## Local AI

- Ollama connection test passes
- Selected Ollama model works
- Timeout setting is respected
- App does not freeze during generation/review/improvement

## Packaging

- `scripts/build_windows.ps1` finishes without errors
- `dist/ResuBuilder/ResuBuilder.exe` launches
- Assets are bundled
- No console window opens during normal app use

## GitHub

- README explains installation and usage
- Screenshots are updated
- Branch is merged into `main`
- Version tag is created only after package test passes
