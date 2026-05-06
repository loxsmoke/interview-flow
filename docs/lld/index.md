# Low-Level Design — Interview Flow

## Architecture Overview

```mermaid
classDiagram
    direction TB

    class InterviewState {
        +str id
        +str job_posting
        +str resume
        +str company_name
        +str position
        +list~Resume~ resumes
        +CompanyResearch research
        +InterviewIntel interview_intel
        +JDAnalysis jd_analysis
        +list~Story~ stories
        +list~MockSession~ mock_sessions
        +CompData comp_data
        +Pitch pitch
        +str resume_review
        +str tailored_resume
        +str concerns_analysis
        +list~ProgressEntry~ progress
        +list~str~ completed_steps
        +str current_step
    }

    class Resume {
        +str id
        +str description
        +str text
    }

    class Story {
        +str id
        +str title
        +str situation
        +str task
        +str action
        +str result
        +str earned_secret
        +list~str~ tags
        +dict fit_scores
    }

    class MockSession {
        +str id
        +str format
        +list~InterviewQuestion~ questions
        +dict overall_scores
        +str summary
    }

    class CompanyResearch {
        +str raw_report
        +str researched_at
        +int fit_score
        +float query_cost_usd
        +str query_model_name
    }

    class InterviewIntel {
        +str raw_report
        +float query_cost_usd
        +str query_model_name
    }

    class JDAnalysis {
        +str raw_analysis
        +list~str~ requirements
        +float query_cost_usd
    }

    class CompData {
        +str raw_analysis
        +int range_low
        +int range_high
        +float query_cost_usd
    }

    class Pitch {
        +str value_proposition
        +str elevator_10s
        +str interview_90s
        +float query_cost_usd
    }

    class CustomAction {
        +str id
        +str name
        +str prompt_template
    }

    InterviewState *-- "0..*" Resume
    InterviewState *-- CompanyResearch
    InterviewState *-- InterviewIntel
    InterviewState *-- JDAnalysis
    InterviewState *-- CompData
    InterviewState *-- Pitch
    InterviewState *-- "0..*" Story
    InterviewState *-- "0..*" MockSession
```

## Package Structure

```
interview-workflow/
├── app/
│   ├── main.py                 # FastAPI routes and orchestration
│   ├── models.py               # Pydantic data models
│   ├── state.py                # JSON file persistence layer
│   ├── queue_manager.py        # Background queue for agent tasks + SSE
│   ├── prompt_loader.py        # Agent prompt template loader
│   ├── desktop.py              # Native desktop window launcher
│   ├── tracing.py              # Langfuse observability integration
│   └── agents/
│       ├── streaming.py        # Provider abstraction (Claude/OpenAI/Ollama) + cost tracking
│       ├── research.py         # Company research agent
│       ├── story_miner.py      # Story mining, JD decode, salary, concerns, pitches, intel
│       ├── mock_interview.py   # Multi-turn mock interview session
│       └── resume_chat.py      # Interactive resume coaching chat
├── app/static/
│   └── index.html              # React SPA frontend
├── data/                       # Runtime state files (gitignored)
├── tests/
│   ├── app/                    # Unit and integration tests
│   │   ├── conftest.py         # SDK mocking setup
│   │   └── ...
│   └── e2e/                    # End-to-end Playwright tests
└── docs/
    ├── hld/                    # High-level design
    └── lld/                    # Low-level design (this directory)
```

## Component Documentation

### Models
- [models.md](models.md) — All Pydantic data models: InterviewState, Story, MockSession, CompanyResearch, InterviewIntel, JDAnalysis, CompData, Pitch, Resume, CustomAction, ProgressEntry, and request/response schemas

### State Management
- [state.md](state.md) — Combined JSON file persistence with atomic writes, path traversal prevention, global async locking, and custom actions persistence

### Queue System
- Queue manager (`app/queue_manager.py`) — In-memory background processing queue with SSE event streaming; one task runs at a time, ordered by `SECTION_ORDER`

### Agents
- [agents/research.md](agents/research.md) — Company research agent using web search
- [agents/story_miner.md](agents/story_miner.md) — Story extraction, interview intel, JD decoding, salary coaching, concern anticipation, pitch building
- [agents/mock_interview.md](agents/mock_interview.md) — Multi-turn mock interview session manager
- [agents/resume_chat.md](agents/resume_chat.md) — Interactive resume coaching chat session

### API Routes
- [routes.md](routes.md) — All FastAPI endpoints with request/response schemas and flow diagrams

### Frontend
- [frontend.md](frontend.md) — React SPA architecture, component hierarchy, and API integration
