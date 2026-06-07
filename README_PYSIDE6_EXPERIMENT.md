# ResuBuilder PySide6 Interface

ResuBuilder now uses the PySide6/Qt interface as the primary desktop application.

Run the app:

```bash
python app.py
```

Run the legacy GUI only as a fallback:

```bash
python app_legacy.py
```

## Main capabilities

- Structured profile and evidence collection
- Structured job input
- Job fit analysis
- Tailored CV generation
- Tailored covering-letter generation
- Quality checks and AI review
- Quality-fix improvement workflow
- PDF and application package export
- Workspace save/load
- Theme selection and settings persistence

## Notes

The PySide6 interface is the primary UI. The legacy GUI is retained temporarily as a fallback while packaging and release testing continue.

## Step 26C cleanup

- Load Profile now opens a file picker in the profile data folder instead of silently loading a fixed file.
- Load Workspace now opens from the saved workspace folder preference.
- The default Evidence Builder example is now generic instead of project-specific.
