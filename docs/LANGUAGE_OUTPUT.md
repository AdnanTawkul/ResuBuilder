# Output language support

ResuBuilder currently supports generated document output in:

- English
- German

When German is selected, the AI prompt instructs the selected provider to translate necessary candidate, job, and evidence information into natural professional German. The prompt also instructs the AI to preserve names, email addresses, phone numbers, URLs, company names, product names, programming languages, libraries, frameworks, model names, dates, degree names, and exact numbers unless German wording is clearly standard.

## Current limitation

The deterministic rule-based quality checker is still mostly optimized for English keyword matching. German CVs and covering letters should therefore be reviewed with the AI Quality Review and a manual pass before export.
