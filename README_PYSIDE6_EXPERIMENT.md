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
- Generate CV
- Generate covering letter
- Background generation worker with crash logging
- Deterministic quality check in the Review page
- Settings read from `data/settings.json`

Still placeholder or partial:

- Workspace save/load
- Structured Evidence Builder
- Job Fit Analyzer
- AI Quality Review
- Improve with Quality Fixes
- PDF export
- Application package export

## Run

```bash
python app_qt.py
```

Keep the existing app available:

```bash
python app.py
```

## Debug log

The Qt experiment writes GUI errors to:

```text
data/logs/qt_gui.log
```

## Rule

Do not merge this branch into `main` until the Qt interface reaches feature parity with the existing GUI.
