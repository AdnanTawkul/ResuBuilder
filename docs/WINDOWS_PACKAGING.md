# Windows Packaging Guide

This document prepares ResuBuilder for a local Windows executable build.

## Before building

Confirm the app works from source:

```powershell
python app.py
```

Confirm the legacy GUI still opens if needed:

```powershell
python app_legacy.py
```

## Optional icon

The app loads the SVG logo from:

```text
src/resume_ai/assets/resubuilder_logo.svg
```

For the Windows `.exe` icon, add an ICO file here:

```text
src/resume_ai/assets/resubuilder_icon.ico
```

The SVG logo is the design source. The `.ico` file is only for Windows executable packaging.

## Build

From the project root, run:

```powershell
scripts\build_windows.ps1
```

Or:

```cmd
scripts\build_windows.bat
```

The executable folder will be created at:

```text
dist/ResuBuilder/
```

Run:

```text
dist/ResuBuilder/ResuBuilder.exe
```

## Do not commit build output

The following folders should stay ignored by Git:

```text
build/
dist/
*.spec.bak
```

## Packaging test checklist

- App launches from `dist/ResuBuilder/ResuBuilder.exe`
- Logo appears
- Profile loads
- Ollama settings are visible
- CV generation works with Ollama running
- Covering letter generation works
- Quality check works
- PDF export works
- Application package export works
- Workspace save/load works

Do not publish a release until this checklist passes.
