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

## Next

1. Add Qt Job Fit Analyzer.
2. Add Qt AI Quality Review and Improve with Quality Fixes.
3. Add settings editing inside the Qt Settings page.
4. Decide whether Qt replaces the old GUI.

## Step 24J, Qt Evidence Builder

- Added Evidence page to the Qt experiment.
- Added structured evidence fields and actions.
- Saves and restores evidence through profile JSON and workspace JSON.
- Passes structured evidence into generation via `CandidateProfile.structured_evidence`.


## Step 24K - Qt evidence workspace restore fix

- Stores structured evidence entries explicitly in Qt workspace snapshots.
- Restores evidence from both profile-level and top-level workspace fields.
- Shows structured evidence block count in the workspace status panel.
