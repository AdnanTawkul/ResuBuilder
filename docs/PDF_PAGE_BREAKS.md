# Manual PDF page breaks

ResuBuilder can insert manual page split markers into generated CV text.

Use this when a section should begin on a new PDF page, for example when you want the section after **Education** to start cleanly on the next page.

## How to use

1. Generate a CV.
2. Open **Review**.
3. Select **CV** as the document.
4. In **Manual PDF page breaks**, click **Refresh Sections**.
5. Choose the section after which the page should split.
6. Click **Add Page Split After Section**.
7. Export the CV PDF and visually inspect the result.

## Behavior

Manual page splits are stored inside the generated CV as a hidden Markdown comment marker:

```markdown
<!-- RESUBUILDER_PAGE_BREAK -->
```

The PDF exporter converts that marker into a real page break.

## Limits

- Manual page splits are intended for CV sections, not covering letters.
- A page split only affects PDF export.
- If a section is very long, it may still continue across pages after it starts.
- Always inspect the exported PDF before sending an application.
