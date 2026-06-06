# Roadmap

## Completed

- Basic GUI
- Candidate profile input
- Job description input
- Existing CV and covering letter input
- Markdown generation
- PDF export
- PDF templates
- OpenAI provider
- Ollama local AI provider
- Quality checker
- AI quality review
- Regenerate with quality fixes
- AI review wait screen fix
- Quality improvement wait screen
- Quality improvement timeout guard
- Ollama non-thinking request mode
- Improved AI output structure
- Better job keyword extraction
- Candidate evidence mapping
- Contact-header repair for generated documents
- Truth-aware quality scoring
- Supported vs unsupported job signal reporting
- Quality-fix prompts that avoid impossible keyword chasing
- Application workspace save/load
- PDF/text import for job descriptions, existing CVs, and existing covering letters
- Replaced resume generation with covering letter generation
- Added covering-letter-specific AI prompt and quality-check logic
- Added one-click application package export
- Added package folders with CV PDF, covering letter PDF, quality report, and summary JSON
- Added structured evidence builder for stronger AI inputs
- Added AI-powered Job Fit Analyzer using Ollama before generation
- Added app settings persistence for AI, templates, PDF, and folders
- Replaced crowded tabs with a sidebar workflow and skip options
- Removed redundant Next navigation from the sidebar workflow
- Added modern GUI visual polish with cleaner spacing, typography, sidebar highlighting, and styled text areas

## Next

1. Add guided questions for unsupported job signals.
2. Feed job fit strategy into quality improvement history and document versioning.
3. Add document version history inside each application workspace.
4. Add template preview and editing.
5. Add PDF template customization.
6. Package the app as a Windows executable.


## Step 20 bugfix

- Prompt preview opens in a dedicated window.
- Removed outdated Output tab wording from user-facing messages.

## Step 20 navigation cleanup

- Removed redundant **Next** button.
- Kept **Back**, **Skip & Continue**, and **Complete & Continue**.
- Completion now advances the user automatically to the next workflow step.


## Step 21 modern GUI polish

- Added a modern theme layer for the existing sidebar workflow.
- Increased default window size.
- Added active-step sidebar highlighting.
- Added distinct complete and warning sidebar styles.
- Styled text areas for better readability.
- Added CustomTkinter dependency for a modern UI base while keeping the existing workflow logic stable.

- Step 21 follow-up: cleaned the Export step controls to avoid cropped action buttons at normal window sizes.
