# ResuBuilder Qt Primary Migration

The PySide6/Qt GUI is now the primary ResuBuilder interface.

## Run the main app

```bash
python app.py
```

## Run the legacy Tkinter GUI

```bash
python app_legacy.py
```

## Keep temporarily

Do not delete the legacy GUI yet:

```text
src/resume_ai/gui.py
app_legacy.py
```

Keep it until the Qt version has been used through several full test applications without workflow regressions.

## Main verification flow

1. Load or create a workspace.
2. Load saved profile.
3. Add structured evidence.
4. Fill the structured Job page.
5. Analyze job fit.
6. Generate CV.
7. Generate covering letter.
8. Run quality check.
9. Run AI quality review.
10. Improve with quality fixes.
11. Export selected PDFs.
12. Export application package.
13. Save workspace.
14. Close and reopen the app.
15. Reload workspace and confirm all data is restored.

## GitHub guidance

Recommended commit:

```text
Make PySide6 GUI the primary app entry point
```

Keep this on the Qt experiment branch until you are ready to merge into `main`.
