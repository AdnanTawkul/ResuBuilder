# Known Limitations

ResuBuilder is functional, but it is still an early release candidate.

## AI limitations

- AI-generated CVs and covering letters must be manually reviewed.
- The app tries to prevent unsupported claims, but it cannot guarantee factual accuracy.
- Local AI output quality depends on the selected Ollama model and hardware.
- OpenAI usage requires a valid API key, billing, and quota.

## Document limitations

- PDF import supports selectable-text PDFs only.
- Scanned image-only PDFs are not supported yet.
- OCR is not implemented.
- PDF template customization is limited.
- DOCX export is intentionally not supported at this stage.

## Workflow limitations

- Multi-user account support is not implemented.
- Cloud sync is not implemented.
- Automatic application tracking across job boards is not implemented.
- The quality score is a heuristic and should not be treated as absolute truth.

## Packaging limitations

- Windows packaging is supported through PyInstaller.
- macOS and Linux packaging are not prepared yet.
- The executable still depends on external local services such as Ollama if local AI is selected.

## Privacy limitations

- Saved profiles and workspaces are local JSON files.
- Users must avoid committing `data/`, `exports/`, PDFs, and personal workspace files.
- API keys should never be stored in source files or committed to GitHub.
