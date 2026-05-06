# resume-template.docx — Style Reference

`resume-template.docx` is the Word template used when exporting a tailored resume from the app.
Place this file in the same `data/` directory as the workflow JSON files.

When the template is present the app copies it, wipes its body content, and repopulates it using
the styles defined below — so all fonts, spacing, colours, and page margins come from the template.
When the template is absent the app falls back to a plain document with no custom formatting.

---

## Required paragraph styles

The app maps each tagged resume line to a named Word paragraph style.
Every style listed below must exist in the template by **exact name** (matching is case-insensitive
internally, but the name in the document should use the capitalisation shown here).
If a style is missing the paragraph falls back to the built-in **Normal** style.

| Style name | Tag in resume text | Usage |
|---|---|---|
| `Name` | *(automatic)* | Full name — always the first paragraph. Text comes from **Settings → Resume Info → Full name**. |
| `Contact line` | *(automatic)* | Contact details — always the second paragraph. Text comes from **Settings → Resume Info → Contact info**. |
| `Section Heading` | `[Section Heading]` | Title of each major resume section (e.g. *Professional Experience*, *Technical Skills*). The Summary section heading is intentionally suppressed — no heading is written before the summary paragraph. |
| `Summary` | `[Summary]` | Professional summary paragraph(s) that appear at the top of the resume. |
| `Job title` | `[Job title]` | One-line role entry in the format `Job Title \| Company \| Location \| Date range`. |
| `Job summary` | `[Job summary]` | Optional short paragraph immediately after a job title describing the scope of the role. |
| `Job bullet` | `[Job bullet]` | Achievement or responsibility bullet under a job. The bullet character itself should come from the style's list format, not the text. |
| `Skill` | `[Skill]` | One skill category per line in the format `Category: skill1, skill2, …`. The text up to and including the colon is rendered **bold** automatically; the rest is rendered in the normal run weight. |
| `Additional info` | `[Additional info]` | Catch-all for education degrees, certifications, early roles without full detail, awards, and other brief entries. |

---

## Style design guidelines

These are recommendations for how each style should look to produce a clean, ATS-friendly resume.

- **Name** — large font (16–20 pt), bold, centred or left-aligned.
- **Contact line** — small font (9–10 pt), centred, with adequate space below.
- **Section Heading** — all-caps or small-caps, with a bottom border or rule, space-before ~8 pt.
- **Summary** — normal body font, space-after ~6 pt.
- **Job title** — bold, space-before ~6 pt, space-after ~0 pt.
- **Job summary** — normal or italic, space-after ~2 pt.
- **Job bullet** — hanging indent, bullet list format, space-after ~1–2 pt.
- **Skill** — normal body font, space-after ~1–2 pt. The bold category prefix is applied in code so the style itself should use a normal weight.
- **Additional info** — small font (9–10 pt), space-after ~1–2 pt. Alignment may be centred or left-aligned depending on preference.

---

## How the template is applied

1. The app copies `resume-template.docx` to a temporary file.
2. All body paragraphs are removed from the copy (page size, margins, and headers/footers are preserved).
3. The name and contact line are written first using the **Name** and **Contact line** styles.
4. Each tagged line in the resume text is written as a new paragraph using its mapped style.
5. Untagged lines (legacy or plain-text resumes) are written as unstyled **Normal** paragraphs.
6. The finished document is returned to the browser or saved to disk.
