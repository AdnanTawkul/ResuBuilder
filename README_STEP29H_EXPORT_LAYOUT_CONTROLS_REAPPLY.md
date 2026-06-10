# ResuBuilder Step 29H: Reapply Export Layout Controls

This update ensures the Qt Export page contains the CV template preview and section ordering controls.

## Files to copy

- `src/resume_ai/qt_gui.py`
- `src/resume_ai/pdf_exporter.py`
- `src/resume_ai/pdf_templates.py`
- `src/resume_ai/document_layout.py`
- `docs/PDF_TEMPLATE_LAYOUT.md`

## Verification

After copying, run:

```powershell
Select-String -Path .\src\resume_ai\qt_gui.py -Pattern "Template preview and section order"
```

If it returns a line, the source file contains the new UI.

Run from source:

```powershell
python app.py
```

Open Export. You should see a card named **Template preview and section order** between Export settings and Export actions.

If you test the executable, rebuild first:

```powershell
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
scripts\build_windows.ps1
```
