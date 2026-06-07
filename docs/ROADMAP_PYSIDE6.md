# PySide6 GUI Roadmap

## Done

- Add Qt shell beside the existing GUI.
- Add modern dark-blue theme.
- Add Profile page with validation.
- Add profile save/load and JSON import/export.
- Connect generation to existing AI service.
- Stabilize background generation worker.
- Add deterministic quality check page.
- Add Qt PDF export.
- Add Qt application package export.
- Fix Export page field sizing.
- Add scrollable Export page and wider scrollbars.
- Add Qt Workspace save/load.
- Add Qt Evidence Builder.
- Add Qt Job Fit Analyzer inside the Generate page.
- Add dedicated Qt Job page and remove redundant Export company/role fields.
- Add Qt AI Quality Review and Improve with Quality Fixes.
- Add editable Qt Settings page.

## Next

1. Complete feature parity test against the old GUI.
2. Decide whether Qt replaces the old GUI.
3. Prepare Qt replacement plan or keep both app launchers temporarily.

## Step 24J, Qt Evidence Builder

- Added Evidence page to the Qt interface.
- Added structured evidence fields and actions.
- Saves and restores evidence through profile JSON and workspace JSON.
- Passes structured evidence into generation via `CandidateProfile.structured_evidence`.


## Step 24K - Qt evidence workspace restore fix

- Stores structured evidence entries explicitly in Qt workspace snapshots.
- Restores evidence from both profile-level and top-level workspace fields.
- Shows structured evidence block count in the workspace status panel.


## Step 24L quiet dialog update

The Qt interface now uses custom silent confirmation and information dialogs instead of native QMessageBox convenience windows. This prevents Windows notification sounds when saving workspaces, loading profiles, exporting files, or showing validation messages.


## Step 24M - Qt Job Fit Analyzer inside Generate

- Added Ollama job-fit analysis inside the Generate page above the generation controls.
- Saves and restores job fit analysis in workspace JSON files.
- Sends the stored strategy into document generation so it affects CV and covering-letter output.


## Step 24N - Qt structured Job page

- Added a Job page for company, job title, full job description, key responsibilities, and required experience/skills.
- Removed redundant company and role inputs from the Export page.
- Uses structured job details in generation, job fit, quality check, workspace save/load, and application package export.


## Step 24O - Qt AI Quality Review and Improve with Quality Fixes

- Added AI Quality Review to the Qt Review page.
- Added Improve with Quality Fixes for the selected document.
- Review and improvement use the existing AI service backend.
- Long-running AI review/improvement tasks run in background threads.
- Workspace save/load now preserves AI quality review text.

## Step 24P - Qt Settings page completion

- Added editable settings inside the Qt Settings page.
- Added AI provider/model/timeout controls.
- Added document template, PDF template, and page-size defaults.
- Added workspace/export folder defaults.
- Added Light, Dark, and Dark blue Qt theme switching.
- Settings persist through `data/settings.json`.

## Step 24Q - Qt Settings model dropdown cleanup

- Replaced free-text model fields with dropdowns for Ollama and OpenAI.
- Preserves saved custom model values as dropdown choices.
- Improved timeout spinner arrow styling and spacing.

## Step 24R. Qt dropdown arrow visibility fix

- Replaced CSS triangle combo-box arrows with SVG chevron assets.
- Made dropdown hit areas wider and easier to see in Light, Dark, and Dark blue themes.
- Kept the timeout spinner styling from the previous settings cleanup.


### Step 24S, Qt dropdown and spinner arrow polish

- Centered dropdown chevron indicators.
- Replaced AI timeout spinner triangles with matching SVG chevrons.
- Added reusable up-chevron SVG assets for light and dark themes.

### Step 24T, Qt top menu expansion

- Added top-level menus for Workspace, Profile, Evidence, Job, Generate, Review, Export, and Settings.
- Kept Workflow as a global navigation menu.
- Added direct top-menu actions for common workflows so users are not forced to rely only on the sidebar.

## Step 24U - Compact top menu cleanup

Status: added.

The Qt menu bar now matches the simpler legacy structure with only File, Settings, and Help. Sidebar navigation remains the primary page navigation. The top menu is reserved for application-level actions, quick settings, and help.

## Step 24V: Settings dialog color repair

- Repaired settings window background colors so dialog chrome, scroll area, cards, and footer use the active theme consistently.
- Removed the gray/black background leak around the settings cards in Dark blue, Dark, and Light themes.


## Step 24W: Compact sidebar cleanup

- Removed the redundant Settings item from the left sidebar.
- Settings now lives only in the top Settings menu and standalone settings window.
- Sidebar is reserved for workflow pages only.


## Step 24X menu width polish

- Top dropdown menus now auto-size to the longest visible action.
- Menu item padding was increased so labels such as Restore App Settings do not get clipped.
- The menu polish applies across Light, Dark, and Dark blue themes.

## Step 24Z. Modern 3D theme

Status: implemented in the PySide6 interface.

Changes:

- Added Modern 3D Light and Modern 3D Dark theme options.
- Styled cards, inputs, buttons, menus, scrollbars, and sidebar states with a soft neumorphic/3D direction.
- Extended theme persistence so both new options survive app restart.

Next check:

- Verify that the 3D themes look good across Welcome, Profile, Evidence, Job, Generate, Review, Export, and Settings.
- Do not remove the existing Light, Dark, and Dark blue themes until the new visual direction is tested thoroughly.


## Current polish task

- Modern 3D interaction polish: horizontal scrollbar removal, floating cards, inset pressed buttons, rounded scrollbars, and wider menus.

### Step 24AB . Rounded scrollbar handle polish
- Force vertical and horizontal scrollbar handles to render as rounded pill controls.
- Keep existing theme-specific colors and gradients.
