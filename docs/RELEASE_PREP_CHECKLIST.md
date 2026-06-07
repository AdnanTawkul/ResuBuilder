# Release Prep Checklist

Use this checklist before creating a GitHub release.

## Source checks

- [ ] `python app.py` launches the Qt app.
- [ ] `python app_legacy.py` launches the legacy GUI.
- [ ] No visible experimental wording remains in the primary app.
- [ ] App title is ResuBuilder.
- [ ] Logo appears in the app.
- [ ] Settings save and restore correctly.
- [ ] Theme switching works.
- [ ] Profile validation works.

## Workflow checks

- [ ] Profile load works.
- [ ] Profile save works.
- [ ] Profile import/export works.
- [ ] Workspace save/load works.
- [ ] Evidence save/load works.
- [ ] Job page fields save/load correctly.
- [ ] Job fit analysis runs.
- [ ] CV generation works.
- [ ] Covering letter generation works.
- [ ] Quality check works.
- [ ] AI quality review works.
- [ ] Improve with quality fixes works.
- [ ] PDF export works.
- [ ] Application package export works.

## Packaged executable checks

- [ ] Clean old `build/` and `dist/` folders.
- [ ] Build with `scripts/build_windows.ps1`.
- [ ] `dist/ResuBuilder/ResuBuilder.exe` launches.
- [ ] Packaged app can generate CV.
- [ ] Packaged app can generate covering letter.
- [ ] Packaged app can run quality check.
- [ ] Packaged app can export PDF.
- [ ] Packaged app can export application package.
- [ ] Packaged app can save/load workspace.
- [ ] Packaged app has no experimental labels.

## Repository checks

- [ ] `build/` is not committed.
- [ ] `dist/` is not committed.
- [ ] `data/` is not committed.
- [ ] `exports/` is not committed.
- [ ] No API keys are committed.
- [ ] README is up to date.
- [ ] CHANGELOG is up to date.
- [ ] Known limitations are documented.
- [ ] Screenshots are added or screenshot placeholders are clearly marked.

## GitHub release checks

- [ ] Create tag `v0.1.0`.
- [ ] Upload zipped Windows build as a release asset.
- [ ] Include release notes.
- [ ] Mention local AI requires Ollama.
- [ ] Mention OpenAI requires separate API billing/quota.
- [ ] Mention this is an early release candidate.
