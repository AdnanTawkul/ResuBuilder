# PySide6 GUI Experiment Roadmap

## Current goal

Prove that PySide6 can replace the current desktop GUI without breaking the existing ResuBuilder backend.

## Step 24A

- Add PySide6 app shell
- Add Welcome page
- Add Profile page
- Add Generate page
- Keep old GUI alive

## Step 24B

- Stabilize background generation in the Qt prototype
- Add debug logging to `data/logs/qt_gui.log`
- Prevent silent generation failures from hiding useful diagnostics

## Next steps

1. Wire workspace save/load.
2. Wire structured evidence builder.
3. Wire job fit analyzer.
4. Wire quality review.
5. Wire PDF/package export.
6. Decide whether Qt should replace the old GUI.
