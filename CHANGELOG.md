# Changelog

All notable changes to ResuBuilder will be documented in this file.

## [0.1.0] - Release candidate

### Added

- PySide6/Qt primary desktop interface.
- Legacy GUI preserved through `app_legacy.py`.
- Local AI generation using Ollama.
- Optional OpenAI provider support.
- Structured profile form with email and telephone validation.
- Profile save/load/import/export.
- Structured evidence builder.
- Structured job page with company, job title, full description, responsibilities, and required skills.
- Job fit analyzer integrated into the Generate page.
- Tailored CV generation.
- Tailored covering letter generation.
- Rule-based quality checker.
- AI quality review.
- Improve with quality fixes workflow.
- PDF export for selected documents.
- Full application package export.
- Workspace save/load.
- Settings persistence.
- UI themes: Light, Dark, Dark blue, Modern 3D Light, Modern 3D Dark.
- Silent custom dialogs instead of Windows notification sounds.
- SVG logo support.
- Custom rounded scrollbars.
- Windows packaging scripts.

### Changed

- Replaced resume generation with covering letter generation to avoid redundant CV/resume outputs.
- Made the Qt GUI the primary app entry point through `app.py`.
- Removed visible experimental wording from the primary app.
- Improved profile and workspace loading behavior in the packaged executable.
- Replaced personal default evidence example with a generic example.

### Known limitations

- The application is still a release candidate.
- OCR for scanned PDFs is not supported.
- AI output must still be manually verified before submission.
- OpenAI API usage requires separate OpenAI billing and quota.
- Ollama must be installed and running for local AI workflows.
