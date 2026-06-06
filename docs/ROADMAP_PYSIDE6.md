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

## Next

1. Add Qt Workspace save/load.
2. Add Qt Evidence Builder.
3. Add Qt Job Fit Analyzer.
4. Add Qt AI Quality Review and Improve with Quality Fixes.
5. Add settings editing inside the Qt Settings page.
6. Decide whether Qt replaces the old GUI.


## Step 24G, Qt scrollbar and background cleanup

- Fixed dark-blue scroll area background bleed that appeared as brown gaps between cards.
- Restyled vertical and horizontal scrollbars with wider, higher-contrast handles.
- Applied consistent page and scroll-content backgrounds across Profile and Export.

## Step 24H, Generate page layout cleanup

- Added a scrollable Generate page.
- Fixed clipped generation controls at default window size.
- Improved text area height for job description and generated output.
