# Step 29F . German output language support

This update adds an output-language selector for generated documents.

## Added

- Output language selector on the Generate page.
- Supported output languages:
  - English
  - German
- German generation instructions tell the AI to translate necessary candidate, job, and evidence information into professional German while preserving names, emails, URLs, tools, libraries, model names, dates, and exact numbers.
- Output language is saved in app settings.
- Output language is saved and restored in application workspaces.
- Top-menu Settings window and settings page now include Output language under document defaults.

## Test

1. Run `python app.py`.
2. Open Generate.
3. Set Output language to German.
4. Generate a CV.
5. Generate a covering letter.
6. Confirm both are written in German.
7. Save workspace.
8. Reload workspace.
9. Confirm Output language is restored.
10. Open Settings and set Output language to German.
11. Save settings, close, reopen, and confirm German remains selected.

## Notes

The rule-based quality checker is still mostly optimized for English keyword matching. For German outputs, use AI Quality Review as the main qualitative check and manually verify the final text.
