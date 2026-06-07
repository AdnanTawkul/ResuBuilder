# Qt Feature Parity Checklist

Use this checklist before merging the PySide6/Qt GUI into `main` as the primary app.

## Entry points

- [ ] `python app.py` opens the Qt app.
- [ ] `python app_legacy.py` opens the legacy Tkinter app.
- [ ] `python app_qt.py` still opens the Qt app, if kept for testing.

## Core workflow

- [ ] Workspace can be created, saved, saved as, and loaded.
- [ ] Profile can be saved, loaded, imported, and exported.
- [ ] Email validation blocks invalid email before generation.
- [ ] Telephone field accepts numbers only.
- [ ] Structured evidence can be added, edited, deleted, saved, and restored.
- [ ] Structured Job page saves and restores company, title, description, responsibilities, and requirements.
- [ ] Job fit analysis works and is restored from workspace.
- [ ] CV generation works.
- [ ] Covering letter generation works.
- [ ] Quality check works for CV and covering letter.
- [ ] AI quality review works.
- [ ] Improve with quality fixes works.
- [ ] Selected PDF export works.
- [ ] Application package export works.
- [ ] Export package includes PDFs, Markdown files, quality report, and application summary JSON.

## Settings and UI

- [ ] Settings open from the top menu.
- [ ] Theme switching works for Light, Dark, Dark blue, Modern 3D Light, and Modern 3D Dark.
- [ ] Settings persist after app restart.
- [ ] Ollama model dropdown works.
- [ ] OpenAI model dropdown works.
- [ ] Timeout field works and restores correctly.
- [ ] No native Windows notification sounds appear from Qt dialogs.
- [ ] Logo appears in the sidebar and Welcome page.
- [ ] Scrollbars render correctly and do not force horizontal scrolling in normal use.

## Regression check

- [ ] Legacy GUI still launches.
- [ ] Legacy GUI still generates documents.
- [ ] Existing saved workspaces still load in Qt where compatible.
- [ ] Private workspace/profile data is not tracked by Git.
