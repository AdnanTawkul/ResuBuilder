# PDF template preview and section ordering

ResuBuilder supports PDF template selection, document preview, and CV section ordering before export.

## Templates

Available PDF templates include:

- ATS Friendly
- Professional
- Modern
- Academic CV
- Compact Tech CV
- Clean European CV
- Research CV

Use ATS Friendly for conservative applications and applicant tracking systems. Use Compact Tech CV for dense technical CVs. Use Research CV for evidence-heavy research or academic profiles.

## Section ordering

The Export page can detect level-2 Markdown sections such as:

```markdown
## Professional Summary
## Skills
## Projects
## Education
## Languages
```

Move sections up or down before exporting. The candidate header and contact details stay at the top.

## Preventing awkward page splits

The PDF exporter tries to keep short `###` subsection blocks together. This helps avoid splitting individual project descriptions across pages.

For best results, structure projects like this:

```markdown
## Projects

### Project Name
- Built X using Y for Z.
- Evaluated results with A and B.
```

Very long sections may still split because forcing a block larger than one page would break the PDF layout.
