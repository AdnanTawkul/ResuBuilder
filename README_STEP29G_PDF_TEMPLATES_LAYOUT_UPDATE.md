# Step 29G: PDF templates, preview, and CV section ordering

This update adds:

- More PDF templates.
- Export-page document preview.
- CV section ordering controls.
- PDF export behavior that keeps short project-style subsections together where possible.
- Documentation in `docs/PDF_TEMPLATE_LAYOUT.md`.

Copy these files into the project:

```text
src/resume_ai/qt_gui.py
src/resume_ai/pdf_exporter.py
src/resume_ai/pdf_templates.py
src/resume_ai/document_layout.py
docs/PDF_TEMPLATE_LAYOUT.md
```

Test with:

```powershell
python app.py
```

Then rebuild the `.exe`:

```powershell
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
scripts\build_windows.ps1
```
