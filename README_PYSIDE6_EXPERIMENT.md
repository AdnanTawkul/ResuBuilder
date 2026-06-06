# ResuBuilder PySide6 Experiment

This branch is an experimental PySide6/Qt interface for ResuBuilder. It does not replace the existing Tk/CustomTkinter app yet.

## Current status

Working in the Qt prototype:

- Modern dark-blue Qt shell
- Sidebar navigation
- Welcome page
- Profile page
- Email validation before generation
- Telephone number-only validation
- Save/load local profile from `data/candidate_profile.json`
- Import/export profile JSON for faster testing
- Generate CV
- Generate covering letter
- Background generation worker with crash logging
- Deterministic quality check in the Review page
- Single-document PDF export
- Single-document Markdown export
- Complete application package export
- Export page uses a scrollable layout so controls do not get clipped on smaller windows
- Wider scrollbars for easier mouse interaction
- Settings read from `data/settings.json`

Still placeholder or partial:

- Workspace save/load
- Structured Evidence Builder
- Job Fit Analyzer
- AI Quality Review
- Improve with Quality Fixes

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

## Export page layout

The Export page is intentionally scrollable. If the window height is small, scroll inside the page instead of manually resizing the whole application. The scrollbars are wider than the default Qt scrollbars so they are easier to grab during testing.

## Export workflow

1. Generate the CV.
2. Generate the covering letter.
3. Run the quality check in the Review page.
4. Open Export.
5. Enter company and role.
6. Export a selected PDF for quick testing, or export the complete application package.

The package contains PDFs, Markdown sources, a quality report, and `application_summary.json`.

## Debug log

The Qt experiment writes GUI errors to:

```text
data/logs/qt_gui.log
```

## Rule

Do not merge this branch into `main` until the Qt interface reaches feature parity with the existing GUI.


## Step 24G, Qt scrollbar and background cleanup

- Fixed dark-blue scroll area background bleed that appeared as brown gaps between cards.
- Restyled vertical and horizontal scrollbars with wider, higher-contrast handles.
- Applied consistent page and scroll-content backgrounds across Profile and Export.
