# Windows Packaging Guide

ResuBuilder uses PyInstaller to build a Windows executable.

## Before building

From the project root, activate the virtual environment:

```powershell
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Clean old builds

```powershell
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
```

## Build

Run:

```powershell
scripts\build_windows.ps1
```

Or:

```cmd
scripts\build_windows.bat
```

## Run the build

```powershell
dist\ResuBuilder\ResuBuilder.exe
```

## Smoke test the executable

Test the packaged `.exe`, not only `python app.py`:

```text
1. Open ResuBuilder.exe
2. Load profile
3. Load or add evidence
4. Fill Job page
5. Analyze job fit
6. Generate CV
7. Generate covering letter
8. Run quality check
9. Run AI quality review
10. Improve with quality fixes
11. Export selected PDF
12. Export application package
13. Save workspace
14. Close app
15. Reopen app
16. Load workspace
17. Confirm everything restored
```

## Do not commit build output

Do not commit:

```text
build/
dist/
*.exe
```

Upload the `.exe` or zipped `dist/ResuBuilder/` folder as a GitHub Release asset instead.

## Common packaging problems

### The executable shows old text

You are running an old build. Delete `build/` and `dist/`, then rebuild.

### Missing logo or icons

Make sure assets are included in the PyInstaller spec file and exist under:

```text
src/resume_ai/assets/
```

### Ollama does not work from the executable

Confirm Ollama is installed and available at:

```text
http://localhost:11434
```

Then test from PowerShell:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```
