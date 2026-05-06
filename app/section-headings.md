# Resume Section Heading Mappings

This file controls how section headings in a resume document are recognised and mapped
to section types that drive tagging behaviour. The app reads this table on every resume
parse, so edits take effect immediately without restarting.

**How it works**

- The app scans each line of the resume for a known section heading.
- If the line matches an entry in the *Input text* column (case-insensitive, after stripping
  markdown formatting and a trailing colon), it is tagged as `[Section Heading]` using the
  original text from the resume, and the corresponding section type determines how the
  following lines are tagged.
- Lines in ALL-CAPS (e.g. `WORK EXPERIENCE`) are always treated as section headings
  regardless of this table.
- Only the first two columns are used. Additional columns are ignored.

**Adding variants**

Add a new row with the section type and the alternative heading text you want to support.
The section type must be one of the four known types listed below.

**Section types and their output behaviour**

| Type | Output behaviour |
|---|---|
| summary | Lines tagged `[Summary]` |
| experience | Lines tagged `[Job title]` / `[Job summary]` / `[Job bullet]` |
| skills | Lines tagged `[Skill]` |
| additional | Lines tagged `[Additional info]` |

---

## Mapping table

| Section type | Input text |
|---|---|
| summary | summary |
| summary | professional summary |
| summary | profile |
| summary | objective |
| summary | career objective |
| summary | about |
| summary | about me |
| summary | overview |
| experience | experience |
| experience | work experience |
| experience | professional experience |
| experience | employment |
| experience | employment history |
| experience | career history |
| experience | work history |
| experience | early career |
| experience | early career experience |
| experience | earlier experience |
| experience | earlier career |
| experience | other experience |
| additional | additional experience |
| skills | skills |
| skills | technical skills |
| skills | technical skills and tools |
| skills | tools & platforms |
| skills | skills & technology |
| skills | core competencies |
| skills | competencies |
| skills | core expertise |
| skills | technologies |
| skills | expertise |
| skills | technical expertise |
| additional | education |
| additional | certifications |
| additional | certificates |
| additional | credentials |
| additional | licenses |
| additional | license & certifications |
| additional | licenses & certifications |
| additional | awards |
| additional | honors |
| additional | honors & awards |
| additional | achievements |
| additional | publications |
| additional | projects and publications |
| additional | conference presentations & speaking |
| additional | projects |
| additional | volunteer |
| additional | volunteering |
| additional | volunteer experience |
| additional | languages |
| additional | interests |
| additional | hobbies |
| additional | activities |
| additional | personal projects |
| additional | additional information |
| additional | additional |
