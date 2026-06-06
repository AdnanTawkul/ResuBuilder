# ResuBuilder PySide6 Experiment

This branch is an experimental PySide6/Qt interface for ResuBuilder. It does not replace the existing Tk/CustomTkinter app yet.

## Current status

Working in the Qt prototype:

- Modern dark-blue Qt shell
- Sidebar navigation
- Welcome page
- Workspace page
- Profile page
- Email validation before generation
- Telephone number-only validation
- Save/load local profile from `data/candidate_profile.json`
- Import/export profile JSON for faster testing
- Structured Evidence Builder page
- Dedicated Job page with company, role, full description, responsibilities, and requirements
- Structured evidence saved inside profiles and workspaces
- Structured evidence included in generation through the existing backend profile model
- Job Fit Analyzer embedded inside the Generate page
- Job fit strategy is included automatically in CV and covering-letter generation
- Job fit analysis saved and restored through workspace JSON files
- Save/load complete application workspace JSON files
- File menu actions for workspace new/load/save/save-as
- Generate CV
- Generate covering letter
- Background generation worker with crash logging
- Deterministic quality check in the Review page
- Single-document PDF export
- Single-document Markdown export
- Complete application package export
- Export page uses a scrollable layout so controls do not get clipped on smaller windows
- Wider scrollbars for easier mouse interaction
- Settings read from and written to `data/settings.json`
- Editable Qt Settings page for AI provider, models, timeout, templates, page size, folders, and theme

Still placeholder or partial:

- Full feature parity review against the old GUI

## Run

```bash
python app_qt.py
```

Keep the existing app available:

```bash
python app.py
```

## Profile testing shortcut

Use the Profile page buttons:

1. Fill profile fields.
2. Click **Save Profile**.
3. Restart the Qt app.
4. Click **Load Saved Profile**.

You can also use **Import Profile JSON** and **Export Profile JSON** to move test profiles around without retyping them.

## Evidence Builder workflow

1. Open **Evidence**.
2. Add one evidence block per project, role achievement, study, or technical proof.
3. Fill tools, methods, outcome, proof, and relevant job signals.
4. Click **Add Evidence**.
5. Save the profile or workspace so the evidence persists.

Good evidence is specific. Bad evidence is vague. Do not add fake metrics or unsupported technologies just to improve a score.


## Job workflow

1. Open **Job**.
2. Enter the company and job title.
3. Paste the full job description.
4. Paste the responsibilities section under **Key responsibilities**.
5. Paste must-have qualifications under **Required experience and skills**.
6. Continue to Generate.

This structured job brief is passed to the job fit analyzer, CV generator, covering-letter generator, quality checker, workspace save/load, and export package metadata.

## Job Fit workflow

1. Open **Generate**.
2. Click **Analyze Job Fit with Ollama** before generating.
4. Review strong alignment, weak alignment, unsupported claims, and generation instructions.
5. Generate the CV or covering letter. The stored job fit strategy is passed automatically into the generation request.
6. Save the workspace so the job fit analysis is restored next time.

The Job Fit Analyzer intentionally runs through Ollama/local AI. It should prevent the generator from chasing unsupported job keywords or inventing evidence.

## Export page layout

The Export page is intentionally scrollable. If the window height is small, scroll inside the page instead of manually resizing the whole application. The scrollbars are wider than the default Qt scrollbars so they are easier to grab during testing.

## Export workflow

1. Generate the CV.
2. Generate the covering letter.
3. Run the quality check in the Review page.
4. Open Export.
5. Confirm company and role are already set on the Job page.
6. Export a selected PDF for quick testing, or export the complete application package.

The package contains PDFs, Markdown sources, a quality report, and `application_summary.json`.

## Debug log

The Qt experiment writes GUI errors to:

```text
data/logs/qt_gui.log
```

## Rule

Do not merge this branch into `main` until the Qt interface reaches feature parity with the existing GUI.

## Step 24J, Qt Evidence Builder

- Added a dedicated Evidence page to the Qt sidebar.
- Added structured evidence fields for type, title, context, tools, methods, outcome, proof, and job signals.
- Added Add, Update, Delete, Clear, and Load Example actions.
- Added evidence prompt preview.
- Saves structured evidence into profile JSON and workspace JSON.
- Includes structured evidence in the `CandidateProfile` passed to the existing generation backend.


## Step 24K - Qt evidence workspace restore fix

- Stores structured evidence entries explicitly in Qt workspace snapshots.
- Restores evidence from both profile-level and top-level workspace fields.
- Shows structured evidence block count in the workspace status panel.


## Step 24L quiet dialog update

The Qt experiment now uses custom silent confirmation and information dialogs instead of native QMessageBox convenience windows. This prevents Windows notification sounds when saving workspaces, loading profiles, exporting files, or showing validation messages.


## Step 24M - Qt Job Fit Analyzer inside Generate

- Added the Job Fit Analyzer directly above the generation controls.
- Runs Ollama job-fit analysis from the Generate page.
- Stores the analysis in the workspace snapshot.
- Passes the analysis into `GenerationRequest.job_fit_analysis` so CV and covering-letter prompts use the strategy automatically.
- Keeps the old GUI untouched.


## Step 24N - Qt structured Job page

- Added a dedicated Job page to the Qt sidebar.
- Moved company, job title, full job description, key responsibilities, and required experience into structured fields.
- Removed redundant company and role fields from the Export page.
- Export filenames and package metadata now use the Job page values.
- Generation, job fit analysis, quality check, workspace save/load, and package export now use a combined structured job brief.

## Step 24O - Qt AI Quality Review and Improve with Quality Fixes

- Added AI Quality Review to the Qt Review page.
- Added Improve with Quality Fixes for the selected CV or covering letter.
- Runs AI review and improvement in background threads.
- Disables review buttons while long AI tasks are running.
- Saves and restores AI quality review text in workspace JSON.
- Includes AI review text in exported quality reports when available.
- Keeps the old GUI untouched.

## Step 24P - Qt Settings page completion

- Replaced the read-only Settings placeholder with editable Qt settings.
- Added controls for AI provider, Ollama URL, Ollama model, OpenAI model, generation mode, and timeout.
- Added document default controls for generation template, PDF template, and page size.
- Added default workspace and export folder fields with Browse buttons.
- Added Light, Dark, and Dark blue theme selection with live preview.
- Settings are saved to `data/settings.json` and applied to Generate, Review, Export, and the Qt theme.

## Step 24Q - Qt Settings model dropdown cleanup

- Replaced free-text Ollama model entry with a dropdown.
- Replaced free-text OpenAI model entry with a dropdown.
- Preserves previously saved custom model names by inserting them into the dropdown if needed.
- Improved AI timeout spinbox styling so the arrows look cleaner and no longer touch the right edge.

## Step 24R. Qt dropdown arrow visibility fix

- Replaced CSS triangle combo-box arrows with SVG chevron assets.
- Made dropdown hit areas wider and easier to see in Light, Dark, and Dark blue themes.
- Kept the timeout spinner styling from the previous settings cleanup.


## Step 24S, Qt dropdown and spinner arrow polish

This update centers the dropdown chevrons and replaces the timeout spinner triangles with matching chevron SVG icons.

Test checklist:

1. Open Settings.
2. Check Ollama model and OpenAI model dropdown arrows.
3. Check AI timeout up/down arrows.
4. Switch between Light, Dark, and Dark blue.
5. Confirm all arrows remain centered and visible.

## Step 24U - Qt compact top menu cleanup

- Reduced the Qt top menu to three menus: File, Settings, and Help.
- Removed duplicated page-specific menus from the top bar.
- File now contains workspace, profile, export, and exit actions.
- Settings now contains Open Settings, quick UI Theme selection, Save App Settings, and Restore App Settings.
- Help now contains Workflow Guide, Options Help, and About ResuBuilder.
- Open Settings now launches a standalone settings window instead of only navigating to the sidebar Settings page.

## Step 24V: Settings dialog color repair

- Repaired settings window background colors so dialog chrome, scroll area, cards, and footer use the active theme consistently.
- Removed the gray/black background leak around the settings cards in Dark blue, Dark, and Light themes.


## Step 24W: Compact sidebar cleanup

- Removed the redundant Settings item from the left sidebar.
- Settings now lives only in the top Settings menu and standalone settings window.
- Sidebar is reserved for workflow pages only.


## Step 24X menu width polish

- Top dropdown menus now auto-size to the longest visible action.
- Menu item padding was increased so labels such as Restore App Settings do not get clipped.
- The menu polish applies across Light, Dark, and Dark blue themes.
