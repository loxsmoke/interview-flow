# Models — Low-Level Design

**File**: `app/models.py`

## Overview

All domain data structures for the Interview Flow system, implemented as Pydantic v2 `BaseModel` classes. These models serve dual purpose: runtime data validation and JSON serialization for persistence.

## ID Generation

```python
def new_id() -> str
```

Generates a 12-character lowercase hex string from `uuid4`. Used as the default ID factory for all entities.

- **Returns**: `str` — 12-char hex (e.g., `"a1b2c3d4e5f6"`)
- **Collision risk**: Negligible for single-user local tool (~2^48 namespace)

---

## Domain Models

### Resume

A saved resume in the resume library. Multiple resumes can be stored per workflow state and reused across states.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `new_id()` | Unique identifier |
| `created_at` | `str` | ISO timestamp | Creation timestamp |
| `description` | `str` | `""` | Short label to distinguish resumes |
| `text` | `str` | `""` | Full resume text |

### CustomAction

A user-defined AI coaching action with a configurable prompt template.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `new_id()` | Unique identifier |
| `name` | `str` | `"Custom Action"` | Display name |
| `description` | `str` | `""` | What this action does |
| `prompt_template` | `str` | `""` | Prompt sent to the AI, may reference `{job_posting}`, `{resume}`, etc. |
| `temperature` | `float \| None` | `None` | Sampling temperature sent to the AI API. `None` = use API default. See table below. |
| `created_at` | `str` | ISO timestamp | Creation timestamp |

#### Temperature values

| Value | Effect |
|-------|--------|
| `None` (empty) | Use API default (~1.0) — temperature parameter is not sent |
| 0.0 – 0.3 | Precise, consistent, near-deterministic — good for structured output |
| 0.4 – 0.6 | Balanced — good for research and synthesis tasks |
| 0.7 – 1.0 | Creative, varied, conversational |
| 1.1 – 2.0 | Highly random — OpenAI only, not supported by Anthropic |

### CustomActionResult

Result from executing a custom action against a workflow state.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `result` | `str` | `""` | AI-generated output text |
| `cost_usd` | `float` | `0.0` | API cost for this run |
| `model_name` | `str` | `""` | Model used |
| `duration_ms` | `int` | `0` | Execution time in milliseconds |
| `ran_at` | `str` | `""` | ISO timestamp of execution |

### Story

Represents a STAR-format interview story extracted from the candidate's experience.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `new_id()` | Unique identifier |
| `title` | `str` | *(required)* | 3-5 word memorable label |
| `situation` | `str` | `""` | Context and challenge (STAR-S) |
| `task` | `str` | `""` | What was specifically required (STAR-T) |
| `action` | `str` | `""` | What the candidate did (STAR-A) |
| `result` | `str` | `""` | Quantified outcomes (STAR-R) |
| `earned_secret` | `str` | `""` | Proprietary insight only someone who lived it would know |
| `tags` | `list[str]` | `[]` | Categories: leadership, technical, conflict, failure, scale, etc. |
| `fit_scores` | `dict[str, str]` | `{}` | Maps question type to fit rating (Strong Fit / Workable / Stretch / Gap) |
| `times_used` | `int` | `0` | How many times this story was used in mock interviews |
| `created_at` | `str` | ISO timestamp | Creation timestamp |

### InterviewQuestion

A single question within a mock interview session.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question` | `str` | *(required)* | The interviewer's question |
| `answer` | `str` | `""` | Candidate's answer |
| `scores` | `dict[str, int]` | `{}` | Dimension scores (1-5): substance, structure, relevance, credibility, differentiation |
| `feedback` | `str` | `""` | Feedback on this answer |
| `interviewer_thoughts` | `str` | `""` | Interviewer's inner monologue |

### MockSession

A completed mock interview session record.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `new_id()` | Unique identifier |
| `format` | `str` | `"behavioral"` | Interview format: behavioral, system_design, case_study, panel, bar_raiser |
| `questions` | `list[InterviewQuestion]` | `[]` | All questions and answers |
| `overall_scores` | `dict[str, float]` | `{}` | Average scores per dimension |
| `bottleneck` | `str` | `""` | Primary dimension holding candidate back |
| `root_cause` | `str` | `""` | Root cause diagnosis |
| `summary` | `str` | `""` | Full debrief text from the AI interviewer |
| `created_at` | `str` | ISO timestamp | Session timestamp |

### CompanyResearch

Research findings about the target company.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `company_name` | `str` | `""` | Company name |
| `summary` | `str` | `""` | Brief overview |
| `culture` | `str` | `""` | Culture assessment |
| `reputation` | `str` | `""` | Sentiment analysis |
| `tech_stack` | `list[str]` | `[]` | Technologies used |
| `products` | `list[str]` | `[]` | Key products/services |
| `challenges` | `list[str]` | `[]` | Business/technical challenges |
| `green_flags` | `list[str]` | `[]` | Positive signals |
| `red_flags` | `list[str]` | `[]` | Warning signals |
| `fit_score` | `int` | `0` | Overall fit 0-100 |
| `raw_report` | `str` | `""` | Full research report markdown |
| `researched_at` | `str` | `""` | Timestamp of research |
| `query_cost_usd` | `float` | `0.0` | API cost for this run |
| `query_model_name` | `str` | `""` | Model used |
| `query_duration_ms` | `int` | `0` | Execution time in milliseconds |
| `query_ran_at` | `str` | `""` | ISO timestamp of execution |

### InterviewIntel

Raw interview process intelligence mined from community sources (Glassdoor, Blind, Reddit, Levels.fyi).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `raw_report` | `str` | `""` | Full intel report markdown |
| `query_cost_usd` | `float` | `0.0` | API cost for this run |
| `query_model_name` | `str` | `""` | Model used |
| `query_duration_ms` | `int` | `0` | Execution time in milliseconds |
| `query_ran_at` | `str` | `""` | ISO timestamp of execution |

### JDAnalysis

Six-lens job description analysis.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `raw_jd` | `str` | `""` | Original job description |
| `requirements` | `list[str]` | `[]` | Hard requirements |
| `nice_to_haves` | `list[str]` | `[]` | Optional qualifications |
| `hidden_signals` | `list[str]` | `[]` | Between-the-lines signals |
| `cultural_cues` | `list[str]` | `[]` | Culture indicators |
| `missing_signals` | `list[str]` | `[]` | Conspicuously absent items |
| `confidence_tags` | `dict[str, str]` | `{}` | Requirement to HIGH/MEDIUM/LOW confidence |
| `raw_analysis` | `str` | `""` | Full analysis text |
| `query_cost_usd` | `float` | `0.0` | API cost for this run |
| `query_model_name` | `str` | `""` | Model used |
| `query_duration_ms` | `int` | `0` | Execution time in milliseconds |
| `query_ran_at` | `str` | `""` | ISO timestamp of execution |

### CompData

Salary and compensation analysis.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `range_low` | `int` | `0` | Low end of estimated range |
| `range_high` | `int` | `0` | High end of estimated range |
| `equity_notes` | `str` | `""` | Equity/RSU analysis |
| `negotiation_scripts` | `list[str]` | `[]` | Ready-to-use negotiation scripts |
| `fallback_language` | `list[str]` | `[]` | Pushback response scripts |
| `raw_analysis` | `str` | `""` | Full salary coaching text |
| `query_cost_usd` | `float` | `0.0` | API cost for this run |
| `query_model_name` | `str` | `""` | Model used |
| `query_duration_ms` | `int` | `0` | Execution time in milliseconds |
| `query_ran_at` | `str` | `""` | ISO timestamp of execution |

### Pitch

Multi-format pitch variants for the candidate.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `elevator_10s` | `str` | `""` | 10-second elevator pitch |
| `networking_30s` | `str` | `""` | 30-second networking pitch |
| `recruiter_60s` | `str` | `""` | 60-second recruiter screen pitch |
| `interview_90s` | `str` | `""` | 90-second "tell me about yourself" |
| `value_proposition` | `str` | `""` | Core value proposition text |
| `talking_points` | `list[str]` | `[]` | Key points to emphasize |
| `thirty_sixty_ninety` | `str` | `""` | 30/60/90 day plan |
| `query_cost_usd` | `float` | `0.0` | API cost for this run |
| `query_model_name` | `str` | `""` | Model used |
| `query_duration_ms` | `int` | `0` | Execution time in milliseconds |
| `query_ran_at` | `str` | `""` | ISO timestamp of execution |

### ProgressEntry

Tracks interview preparation progress over time.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `date` | `str` | ISO timestamp | Entry date |
| `event_type` | `str` | `""` | Type: mock, real_interview, debrief, rejection |
| `notes` | `str` | `""` | Freeform notes |
| `scores` | `dict[str, float]` | `{}` | Dimension scores |
| `self_assessment` | `dict[str, float]` | `{}` | Self-rated scores |

### InterviewState

Master state object for one job opportunity. Contains all inputs, outputs, and workflow tracking.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | `new_id()` | Unique state ID (used in all API paths) |
| `created_at` | `str` | ISO timestamp | Creation time |
| `updated_at` | `str` | ISO timestamp | Last update time (set by state manager on save) |
| `job_posting` | `str` | `""` | Full job description text |
| `resume` | `str` | `""` | Active resume text |
| `resume_raw` | `str` | `""` | Diagnostic raw format from DOCX extraction (temporary) |
| `resumes` | `list[Resume]` | `[]` | Saved resume library for this workflow |
| `custom_action_results` | `dict[str, CustomActionResult]` | `{}` | Results keyed by custom action ID |
| `company_name` | `str` | `""` | Target company name |
| `position` | `str` | `""` | Target position/role title |
| `research` | `CompanyResearch` | `CompanyResearch()` | Research results |
| `interview_intel` | `InterviewIntel` | `InterviewIntel()` | Interview process intel |
| `jd_analysis` | `JDAnalysis` | `JDAnalysis()` | JD decode results |
| `stories` | `list[Story]` | `[]` | Story bank |
| `stories_cost_usd` | `float` | `0.0` | Cost of last story mining run |
| `stories_model_name` | `str` | `""` | Model used for story mining |
| `stories_duration_ms` | `int` | `0` | Story mining execution time |
| `stories_ran_at` | `str` | `""` | Story mining timestamp |
| `mock_sessions` | `list[MockSession]` | `[]` | Completed mock interviews |
| `comp_data` | `CompData` | `CompData()` | Salary analysis |
| `pitch` | `Pitch` | `Pitch()` | Pitch variants |
| `progress` | `list[ProgressEntry]` | `[]` | Progress tracking |
| `resume_review` | `str` | `""` | AI analysis of resume vs JD fit |
| `resume_review_cost_usd` | `float` | `0.0` | Cost of resume review run |
| `resume_review_model_name` | `str` | `""` | Model used for resume review |
| `resume_review_duration_ms` | `int` | `0` | Resume review execution time |
| `resume_review_ran_at` | `str` | `""` | Resume review timestamp |
| `tailored_resume` | `str` | `""` | User-edited tailored resume text |
| `resume_tagged` | `str` | `""` | Heuristic-tagged resume for DOCX export |
| `concerns_analysis` | `str` | `""` | Full concerns anticipation report |
| `concerns_cost_usd` | `float` | `0.0` | Cost of concerns analysis run |
| `concerns_model_name` | `str` | `""` | Model used for concerns analysis |
| `concerns_duration_ms` | `int` | `0` | Concerns analysis execution time |
| `concerns_ran_at` | `str` | `""` | Concerns analysis timestamp |
| `interviewer_concerns` | `list[dict[str, str]]` | `[]` | Anticipated concerns with counter-evidence |
| `thank_you_drafts` | `list[str]` | `[]` | Thank-you note drafts |
| `debrief_notes` | `list[str]` | `[]` | Post-interview debrief notes |
| `completed_steps` | `list[str]` | `[]` | Steps completed so far |
| `current_step` | `str` | `"setup"` | Currently active step |

---

## Request/Response Models

### SetupRequest

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `job_posting` | `str` | *(required, max 100k chars)* | Job description text |
| `resume` | `str` | `""` (max 100k chars) | Resume text |
| `resume_raw` | `str` | `""` (max 500k chars) | Raw diagnostic resume format |
| `company_name` | `str` | `""` (max 500 chars) | Company name |
| `position` | `str` | `""` (max 500 chars) | Position/role title |

### MockInterviewRequest

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"behavioral"` | Interview format |
| `message` | `str` | `""` | Candidate's message (for respond) |
| `session_id` | `str` | `""` | Session key (empty = new session) |

### ChatMessage

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `role` | `str` | *(required)* | `"user"` or `"assistant"` |
| `content` | `str` | *(required)* | Message text |

### StoryRequest

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | `str` | `"mine"` | Action: mine, add, edit, delete |
| `story` | `Story \| None` | `None` | Story data for add/edit |
| `story_id` | `str` | `""` | Story ID for edit/delete |
