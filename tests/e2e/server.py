"""Test server for Playwright e2e tests.

Patches all agent functions with fast mock implementations so tests
run without an Anthropic API key and complete in seconds.
"""

import sys
import types
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Mock claude_agent_sdk before any imports
mock_sdk = types.ModuleType("claude_agent_sdk")
mock_sdk.query = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_sdk.AssistantMessage = type("AssistantMessage", (), {"content": []})
mock_sdk.TextBlock = type("TextBlock", (), {"text": ""})
mock_sdk.ResultMessage = type("ResultMessage", (), {"total_cost_usd": 0.0})
mock_sdk.ToolUseBlock = MagicMock()
mock_sdk.ThinkingBlock = MagicMock()
sys.modules["claude_agent_sdk"] = mock_sdk

# Mock langfuse
mock_langfuse = types.ModuleType("langfuse")
mock_langfuse.Langfuse = MagicMock()
sys.modules["langfuse"] = mock_langfuse

# Keep e2e runs out of the regular app history.
test_data_dir = Path(
    os.environ.get(
        "INTERVIEW_TEST_DATA_DIR",
        str(Path(tempfile.gettempdir()) / "interview-flow-e2e-data"),
    )
)
if test_data_dir.exists():
    shutil.rmtree(test_data_dir)
test_data_dir.mkdir(parents=True, exist_ok=True)
os.environ["INTERVIEW_DATA_DIR"] = str(test_data_dir)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

# Now import and patch the app
import app.agents.research as research_mod
import app.agents.story_miner as story_miner_mod
import app.agents.mock_interview as mock_interview_mod


# --- Mock implementations ---

async def mock_run_research(job_posting: str, resume: str = "") -> dict:
    return {
        "raw_report": (
            "# Company Research Report\n\n"
            "## Company Overview\n"
            "Acme Corp is a mid-stage startup building developer tools.\n\n"
            "## Leadership & Culture\n"
            "Strong engineering culture with flat hierarchy.\n\n"
            "## Reputation & Sentiment\n"
            "[VERIFIED] 4.2/5 on Glassdoor\n\n"
            "## Products & Technology\n"
            "- **Tech Stack**: Python, TypeScript, React, PostgreSQL, Kubernetes\n\n"
            "## Challenges & Opportunities\n"
            "- Scaling to enterprise customers\n\n"
            "---\n"
            "- **Fit Score**: 82/100\n"
            "- **Top Green Flags**: Strong eng culture, growing fast, good reviews\n"
            "- **Top Red Flags**: Small team, fast pace may mean long hours\n"
            "- **Verdict**: Strong opportunity worth pursuing"
        ),
        "cost_usd": 0.05,
    }


async def mock_decode_jd(job_posting: str) -> str:
    return (
        "## JD Analysis\n\n"
        "### 1. Repetition Frequency\n"
        "'distributed systems' appears 4 times — this is their core priority. [HIGH]\n\n"
        "### 2. Order & Emphasis\n"
        "Technical skills listed before soft skills — IC role, not people management. [HIGH]\n\n"
        "### 3. Required vs Nice-to-Have\n"
        "- **Required**: Python, distributed systems, 5+ years\n"
        "- **Nice-to-have**: Kubernetes, ML experience\n\n"
        "### 4. Verb Choices\n"
        "'Own', 'build', 'lead' — high autonomy role. [MEDIUM]\n\n"
        "### 5. Between-the-Lines\n"
        "'Fast-paced' = high workload. 'Self-starter' = limited onboarding. [MEDIUM]\n\n"
        "### 6. What's Missing\n"
        "No mention of work-life balance or team size. [LOW]\n\n"
        "---\n"
        "**The Role**: Senior IC owning a distributed systems vertical.\n"
        "**Hidden Requirements**: Comfort with ambiguity and on-call.\n"
        "**Concerns**: Ask about team size and on-call rotation."
    )


async def mock_mine_stories(resume: str, job_posting: str, existing_stories: str = "None") -> list:
    return [
        {
            "title": "Led Database Migration",
            "situation": "Legacy MySQL was hitting scaling limits at 10K QPS",
            "task": "Plan and execute migration to PostgreSQL with zero downtime",
            "action": "Built dual-write system, migrated tables incrementally over 3 sprints, validated with shadow reads",
            "result": "Zero-downtime migration, 40% cost reduction, 99.99% uptime post-migration",
            "earned_secret": "The hardest part wasn't technical — it was convincing the team to stop feature work for 6 weeks",
            "tags": ["leadership", "technical", "scale"],
            "fit_scores": {
                "leadership": "Strong Fit",
                "technical_challenge": "Strong Fit",
                "conflict": "Workable",
                "failure": "Gap",
                "ambiguity": "Strong Fit",
                "cross_functional": "Workable",
            },
        },
        {
            "title": "Debugging Production Outage",
            "situation": "Payment service went down during Black Friday peak traffic",
            "task": "Identify root cause and restore service within SLA",
            "action": "Led incident response, traced to connection pool exhaustion, deployed hotfix in 23 minutes",
            "result": "Service restored within SLA, implemented circuit breakers to prevent recurrence",
            "earned_secret": "The monitoring dashboard everyone relied on had a 5-minute lag — I found the issue faster by tailing raw logs",
            "tags": ["technical", "failure", "scale"],
            "fit_scores": {
                "leadership": "Workable",
                "technical_challenge": "Strong Fit",
                "conflict": "Gap",
                "failure": "Strong Fit",
                "ambiguity": "Workable",
                "cross_functional": "Stretch",
            },
        },
    ]


async def mock_salary_coach(job_posting: str, resume: str = "") -> str:
    return (
        "## Salary Negotiation Guide\n\n"
        "### Market Range\n"
        "- **Base**: $180K - $250K\n"
        "- **Equity**: 0.05% - 0.15% (4-year vest)\n"
        "- **Signing Bonus**: $20K - $40K\n\n"
        "### Early-Stage Script\n"
        "> 'I'm focused on finding the right fit. I'd love to understand the full comp package before discussing numbers.'\n\n"
        "### Post-Offer Script\n"
        "> 'I'm excited about this offer. Based on my research and experience level, I was targeting $230K base. Is there flexibility?'\n\n"
        "### If They Push Back\n"
        "> 'I understand budget constraints. Could we explore a signing bonus or accelerated equity vesting instead?'"
    )


async def mock_anticipate_concerns(job_posting: str, resume: str) -> str:
    return (
        "## Anticipated Concerns\n\n"
        "### 1. Recent Job Hop (HIGH)\n"
        "**The Concern**: 18 months at last company may signal flight risk.\n"
        "**Counter**: Left for a specific growth opportunity; previous role was 4 years.\n"
        "**Reframe**: 'I made a deliberate move to deepen my distributed systems experience.'\n\n"
        "### 2. Management Gap (MEDIUM)\n"
        "**The Concern**: No formal management title.\n"
        "**Counter**: Led 3-person technical project, mentored 2 junior engineers.\n"
        "**Reframe**: 'I've led cross-functional projects and mentored engineers — I chose to stay technical.'"
    )


async def mock_build_pitches(job_posting: str, resume: str) -> str:
    return (
        "## Your Pitches\n\n"
        "### Core Value Proposition\n"
        "A senior engineer who combines deep distributed systems expertise with a track record of shipping zero-downtime migrations.\n\n"
        "### 10-Second Elevator\n"
        "'I'm a senior engineer specializing in distributed systems — I recently led a zero-downtime database migration serving 10K QPS.'\n\n"
        "### 90-Second Interview\n"
        "'I'm a senior engineer with 8 years building distributed systems...'"
    )


async def _mock_text_stream(text: str, delay: float = 1.0):
    yield {"type": "send", "channel": "user", "text": "Mock prompt"}
    await asyncio.sleep(delay)
    yield {
        "type": "complete",
        "text": text,
        "cost_usd": 0.0,
        "model_name": "mock-model",
        "duration_ms": int(delay * 1000),
    }


def mock_stream_research(job_posting: str, resume: str = ""):
    return _mock_text_stream(
        "# Company Research Report\n\n"
        "## Company Overview\n"
        "Acme Corp is a mid-stage startup building developer tools.\n\n"
        "- **Fit Score**: 82/100"
    )


def mock_stream_decode_jd(job_posting: str):
    return _mock_text_stream(
        "## JD Analysis\n\n"
        "### 1. Repetition Frequency\n"
        "distributed systems appears repeatedly.\n\n"
        "### 2. Order & Emphasis\n"
        "Technical skills listed first."
    )


def mock_stream_interview_intel(company_name: str, job_posting: str):
    return _mock_text_stream(
        "## Interview Intel\n\n"
        "### Real Interview Questions\n"
        "Tell me about distributed systems tradeoffs."
    )


def mock_stream_resume_review(job_posting: str, resume: str):
    return _mock_text_stream(
        "## Resume Review\n\n"
        "### Match Summary\n"
        "Strong distributed systems alignment.",
    )


def mock_stream_mine_stories(resume: str, job_posting: str, existing_stories: str = "None"):
    return _mock_text_stream(json.dumps(mock_mine_stories_payload()))


def mock_mine_stories_payload() -> list:
    return [
        {
            "title": "Led Database Migration",
            "situation": "Legacy MySQL was hitting scaling limits at 10K QPS",
            "task": "Plan and execute migration to PostgreSQL with zero downtime",
            "action": "Built dual-write system, migrated tables incrementally over 3 sprints, validated with shadow reads",
            "result": "Zero-downtime migration, 40% cost reduction, 99.99% uptime post-migration",
            "earned_secret": "The hardest part wasn't technical - it was convincing the team to stop feature work for 6 weeks",
            "tags": ["leadership", "technical", "scale"],
            "fit_scores": {"leadership": "Strong Fit"},
        },
        {
            "title": "Debugging Production Outage",
            "situation": "Payment service went down during Black Friday peak traffic",
            "task": "Identify root cause and restore service within SLA",
            "action": "Led incident response, traced to connection pool exhaustion, deployed hotfix in 23 minutes",
            "result": "Service restored within SLA, implemented circuit breakers to prevent recurrence",
            "earned_secret": "The monitoring dashboard everyone relied on had a 5-minute lag",
            "tags": ["technical", "failure", "scale"],
            "fit_scores": {"technical_challenge": "Strong Fit"},
        },
    ]


def mock_stream_salary_coach(job_posting: str, resume: str = ""):
    return _mock_text_stream(awaitable_salary_text())


def awaitable_salary_text() -> str:
    return (
        "## Salary Negotiation Guide\n\n"
        "### Market Range\n"
        "- **Base**: $180K - $250K\n\n"
        "### Post-Offer Script\n"
        "Ask for flexibility."
    )


def mock_stream_anticipate_concerns(job_posting: str, resume: str):
    return _mock_text_stream(
        "## Anticipated Concerns\n\n"
        "### 1. Recent Job Hop\n"
        "Counter with longer prior tenure.\n\n"
        "### 2. Management Gap\n"
        "Show technical leadership."
    )


def mock_stream_build_pitches(job_posting: str, resume: str):
    return _mock_text_stream(
        "## Your Pitches\n\n"
        "### Core Value Proposition\n"
        "Distributed systems leader.\n\n"
        "### 10-Second Elevator\n"
        "I scale critical systems.\n\n"
        "### 90-Second Interview\n"
        "I bring 8 years of distributed systems experience."
    )


# Patch the mock interview session
class MockMockInterviewSession:
    """Simplified mock interview that returns canned responses."""

    def __init__(self, company_name="", job_posting="", resume="", stories="", interview_format="behavioral"):
        self.interview_format = interview_format
        self.is_complete = False
        self._turn = 0

    async def start(self) -> str:
        return (
            "Hi, I'm Sarah, Engineering Manager at the company. "
            "Thanks for coming in today. Let's start with a behavioral question.\n\n"
            "**Tell me about a time you had to lead a project under tight deadlines. "
            "What was the situation and how did you handle it?**"
        )

    async def respond(self, user_message: str) -> str:
        self._turn += 1
        if self._turn >= 2:
            self.is_complete = True
            return (
                "END_OF_INTERVIEW\n\n"
                "# Interview Debrief\n\n"
                "## Question 1: Leading Under Deadlines\n"
                "- **Substance**: 4/5\n"
                "- **Structure**: 4/5\n"
                "- **Relevance**: 5/5\n"
                "- **Credibility**: 4/5\n"
                "- **Differentiation**: 3/5\n\n"
                "**What worked**: Strong specific examples with metrics.\n"
                "**To improve**: Could have shared more of the 'earned secret'.\n\n"
                "## Overall\n"
                "- **Primary Bottleneck**: Differentiation\n"
                "- **Root Cause**: Narrative hoarding — you have great stories but hold back the spiky details.\n"
                "- **Top Priority**: Practice sharing the uncomfortable, specific insights."
            )
        return (
            "Good answer. Let me follow up on that.\n\n"
            "**You mentioned tight deadlines — how did you handle disagreements "
            "within your team about the technical approach?**"
        )

    async def close(self):
        pass


# Import app AFTER SDK mocks are in place, then patch the references that
# app.main holds (from X import Y creates a local binding — we must patch app_mod.Y)
import app.main as app_mod
import app.agents.streaming as streaming_mod

app_mod.run_research = mock_run_research
app_mod.mine_stories = mock_mine_stories
app_mod.decode_jd = mock_decode_jd
app_mod.salary_coach = mock_salary_coach
app_mod.anticipate_concerns = mock_anticipate_concerns
app_mod.build_pitches = mock_build_pitches
app_mod.stream_research = mock_stream_research
app_mod.stream_decode_jd = mock_stream_decode_jd
app_mod.stream_interview_intel = mock_stream_interview_intel
app_mod.stream_resume_review = mock_stream_resume_review
app_mod.stream_mine_stories = mock_stream_mine_stories
app_mod.stream_salary_coach = mock_stream_salary_coach
app_mod.stream_anticipate_concerns = mock_stream_anticipate_concerns
app_mod.stream_build_pitches = mock_stream_build_pitches
app_mod.require_ai_api_key = lambda: None
app_mod.MockInterviewSession = MockMockInterviewSession
streaming_mod.iter_text_query = lambda *args, **kwargs: _mock_text_stream("Custom output")

if __name__ == "__main__":
    import logging
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    uvicorn.run(app_mod.app, host="127.0.0.1", port=8000)
