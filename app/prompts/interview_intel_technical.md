# Interview Intel — Technical Section

Additional prompt section injected into Interview Intel for technical roles.

## Description

Conditionally appended to the Interview Intel prompt when `_is_technical_role()` returns true based on the position title. Instructs the AI to additionally search for coding problems, system design questions, and domain-specific technical questions reported by candidates.

## Fields

- `{company_name}` — The target company name, used to scope the technical question search

## Prompt

````
### Technical Questions & Problems
List the most commonly reported technical questions and coding problems for this role at <user_provided_company_name>{company_name}</user_provided_company_name>:

**Coding / Algorithm Problems**
- List every specific LeetCode, HackerRank, or other platform problem that candidates reported encountering
- For each problem provide: problem name, difficulty, and a direct link to the problem on that platform
- Group by frequency if possible (multiple candidates reported vs. single report)

**System Design Questions** (if applicable to this role)
- List the most commonly reported system design questions verbatim
- Note which level/round each question appeared in

**Domain-Specific Technical Questions**
- Language or framework-specific questions (e.g. Python internals, React hooks, SQL optimization)
- Architecture or design pattern questions
- Debugging or code-review style questions

---

````
