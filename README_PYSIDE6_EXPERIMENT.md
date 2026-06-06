# ResuBuilder PySide6 Experiment

This branch is an experimental PySide6/Qt interface for ResuBuilder. It must live beside the existing working Tk/CustomTkinter app until it reaches feature parity.

Run the Qt experiment with:

```bash
python app_qt.py
```

Run the existing stable app with:

```bash
python app.py
```

## Current scope

The Qt prototype currently includes:

- Modern dark-blue shell
- Sidebar navigation
- Welcome page
- Profile page
- Email validation
- Telephone number-only validation
- Generate page connected to the existing AI service
- Settings page reading from `data/settings.json`

Review, export, workspace, evidence, and job fit pages are placeholders for now.

## Step 24B stability fix

The generation worker now uses a normal Python background thread with Qt signals instead of a raw QThread worker object. This makes the experimental generation flow easier to debug and avoids worker lifecycle issues while the Qt app is still a prototype.

A debug log is written to:

```text
data/logs/qt_gui.log
```

Do not commit `data/logs/`.
