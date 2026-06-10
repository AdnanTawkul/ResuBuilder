# Step 29D: Profile Sections Update

Adds missing profile fields to the Qt Profile page:

- Education
- Languages
- Links

These values are saved with the profile JSON and workspace JSON, restored when loading, and passed into the existing AI generation backend through the CandidateProfile model.

Copy `src/resume_ai/qt_gui.py` into your project, then test from source and rebuild the executable.
