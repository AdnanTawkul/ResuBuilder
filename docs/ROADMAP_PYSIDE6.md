# PySide6 GUI Experiment Roadmap

## Done

- Add Qt shell beside the existing GUI.
- Add modern dark-blue theme.
- Add Profile page with validation.
- Add profile save/load and JSON import/export.
- Connect generation to existing AI service.
- Stabilize background generation worker.
- Add deterministic quality check page.
- Add Qt PDF export.
- Add Qt application package export.
- Fix Export page field sizing.
- Add scrollable Export page and wider scrollbars.
- Add Qt Workspace save/load.
- Add Qt Evidence Builder.
- Add Qt Job Fit Analyzer inside the Generate page.
- Add dedicated Qt Job page and remove redundant Export company/role fields.
- Add Qt AI Quality Review and Improve with Quality Fixes.
- Add editable Qt Settings page.

## Next

1. Complete feature parity test against the old GUI.
2. Decide whether Qt replaces the old GUI.
3. Prepare Qt replacement plan or keep both app launchers temporarily.

## Step 24J, Qt Evidence Builder

- Added Evidence page to the Qt experiment.
- Added structured evidence fields and actions.
- Saves and restores evidence through profile JSON and workspace JSON.
- Passes structured evidence into generation via `CandidateProfile.structured_evidence`.


## Step 24K - Qt evidence workspace restore fix

- Stores structured evidence entries explicitly in Qt workspace snapshots.
- Restores evidence from both profile-level and top-level workspace fields.
- Shows structured evidence block count in the workspace status panel.


## Step 24L quiet dialog update

The Qt experiment now uses custom silent confirmation and information dialogs instead of native QMessageBox convenience windows. This prevents Windows notification sounds when saving workspaces, loading profiles, exporting files, or showing validation messages.


## Step 24M - Qt Job Fit Analyzer inside Generate

- Added Ollama job-fit analysis inside the Generate page above the generation controls.
- Saves and restores job fit analysis in workspace JSON files.
- Sends the stored strategy into document generation so it affects CV and covering-letter output.


## Step 24N - Qt structured Job page

- Added a Job page for company, job title, full job description, key responsibilities, and required experience/skills.
- Removed redundant company and role inputs from the Export page.
- Uses structured job details in generation, job fit, quality check, workspace save/load, and application package export.


## Step 24O - Qt AI Quality Review and Improve with Quality Fixes

- Added AI Quality Review to the Qt Review page.
- Added Improve with Quality Fixes for the selected document.
- Review and improvement use the existing AI service backend.
- Long-running AI review/improvement tasks run in background threads.
- Workspace save/load now preserves AI quality review text.

## Step 24P - Qt Settings page completion

- Added editable settings inside the Qt Settings page.
- Added AI provider/model/timeout controls.
- Added document template, PDF template, and page-size defaults.
- Added workspace/export folder defaults.
- Added Light, Dark, and Dark blue Qt theme switching.
- Settings persist through `data/settings.json`.
