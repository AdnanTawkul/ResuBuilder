# ResuBuilder Qt Primary Migration

ResuBuilder now uses the PySide6/Qt interface as the primary app shell.

Run the main app:

```bash
python app.py
```

Run the legacy GUI only if you need a fallback:

```bash
python app_legacy.py
```

The legacy GUI should stay available until the Windows package has passed full testing.

## Current status

- Qt interface is primary
- Legacy GUI is retained as backup
- Windows packaging preparation has started
- Do not delete legacy files yet

## Step 26B cleanup

Removed remaining user-facing experimental labels from the primary Qt app, including the sidebar notice and About dialog wording.
