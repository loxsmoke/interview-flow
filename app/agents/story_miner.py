"""Story Mining Agent — extracts compelling STAR stories from resume and experience."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions
from app.agents.streaming import iter_text_query
from app.prompt_loader import load_prompt, load_system_prompt
from app.tracing import traced_agent

logger = logging.getLogger(__name__)

MINING_PROMPT = load_prompt("story_mining")
MINING_SYSTEM_PROMPT = load_system_prompt("story_mining")

RESUME_REVIEW_PROMPT = load_prompt("resume_review")
RESUME_REVIEW_SYSTEM_PROMPT = load_system_prompt("resume_review")


async def stream_mine_stories(resume: str, job_posting: str, existing_stories: str = "None") -> AsyncIterator[dict[str, Any]]:
    """Stream story mining events from iter_text_query."""
    prompt = MINING_PROMPT.format(resume=resume, job_posting=job_posting, existing_stories=existing_stories)
    options = ClaudeAgentOptions(
        system_prompt=MINING_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=5,
        allowed_tools=[],
    )
    async for event in iter_text_query(prompt=prompt, options=options, trace_name="mine-stories"):
        yield event


def build_resume_review_prompt(job_posting: str, resume: str) -> str:
    """Build the resume review prompt."""
    return RESUME_REVIEW_PROMPT.format(job_posting=job_posting, resume=resume)


def build_resume_review_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for resume review."""
    return ClaudeAgentOptions(
        system_prompt=RESUME_REVIEW_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=10,
        allowed_tools=[],
    )


async def stream_resume_review(job_posting: str, resume: str) -> AsyncIterator[dict[str, Any]]:
    """Stream the resume review prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_resume_review_prompt(job_posting, resume),
        options=build_resume_review_options(),
        trace_name="resume-review",
    ):
        yield event


@traced_agent("resume-review", tags=["resume", "tailoring"])
async def review_resume(job_posting: str, resume: str) -> str:
    """Review and tailor a resume against a job description. Returns analysis + tailored draft."""
    analysis = ""
    async for event in stream_resume_review(job_posting, resume):
        if event.get("type") == "complete":
            analysis = event.get("text", "")
    return analysis


@traced_agent("story-mining", tags=["stories", "star-framework"])
async def mine_stories(resume: str, job_posting: str, existing_stories: str = "None") -> list[dict]:
    """Extract STAR stories from resume. Returns list of story dicts."""
    prompt = MINING_PROMPT.format(
        resume=resume,
        job_posting=job_posting,
        existing_stories=existing_stories,
    )

    options = ClaudeAgentOptions(
        system_prompt=MINING_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=5,
        allowed_tools=[],
    )

    raw = ""
    cost_usd = 0.0
    model_name = ""
    duration_ms = 0
    async for event in iter_text_query(prompt=prompt, options=options, trace_name="mine-stories"):
        if event.get("type") == "complete":
            raw = event.get("text", "").strip()
            cost_usd = event.get("cost_usd", 0.0) or 0.0
            model_name = event.get("model_name", "") or ""
            duration_ms = event.get("duration_ms", 0) or 0

    # Strip markdown fences — model sometimes wraps JSON in ```json ... ``` despite instructions
    if "```" in raw:
        if "```json" in raw:
            raw = raw.split("```json")[-1].split("```")[0]
        else:
            raw = raw.split("```")[1].split("```")[0]

    try:
        stories = json.loads(raw.strip())
        if isinstance(stories, list):
            return {"stories": stories, "cost_usd": cost_usd, "model_name": model_name, "duration_ms": duration_ms}
    except json.JSONDecodeError:
        logger.warning("Story mining returned non-JSON (first 200 chars): %s", raw[:200])
        raise ValueError(f"Story mining returned unparseable response. Please try again.")


JD_DECODE_PROMPT = load_prompt("jd_decode")
JD_DECODE_SYSTEM_PROMPT = load_system_prompt("jd_decode")


@traced_agent("decode-jd", tags=["jd-analysis"])
async def decode_jd(job_posting: str) -> str:
    """Decode a job description through 6 lenses. Returns analysis text."""
    analysis = ""
    async for event in stream_decode_jd(job_posting):
        if event.get("type") == "complete":
            analysis = event.get("text", "")
    return analysis


def build_decode_jd_prompt(job_posting: str) -> str:
    """Build the JD decoding prompt."""
    return JD_DECODE_PROMPT.format(job_posting=job_posting)


def build_decode_jd_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for JD decoding."""
    return ClaudeAgentOptions(
        system_prompt=JD_DECODE_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=5,
        allowed_tools=[],
    )


async def stream_decode_jd(job_posting: str) -> AsyncIterator[dict[str, Any]]:
    """Stream the JD decode prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_decode_jd_prompt(job_posting),
        options=build_decode_jd_options(),
        trace_name="decode-jd",
    ):
        yield event


SALARY_PROMPT = load_prompt("salary_coach")
SALARY_SYSTEM_PROMPT = load_system_prompt("salary_coach")


@traced_agent("salary-coaching", tags=["compensation", "web-search"])
async def salary_coach(job_posting: str, resume: str = "") -> str:
    """Generate salary negotiation coaching. Returns analysis text."""
    analysis = ""
    async for event in stream_salary_coach(job_posting, resume):
        if event.get("type") == "complete":
            analysis = event.get("text", "")
    return analysis


def build_salary_prompt(job_posting: str, resume: str = "") -> str:
    """Build the salary coaching prompt."""
    return SALARY_PROMPT.format(job_posting=job_posting, resume=resume or "Not provided")


def build_salary_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for salary coaching."""
    return ClaudeAgentOptions(
        system_prompt=SALARY_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=10,
        allowed_tools=["WebSearch", "WebFetch"],
    )


async def stream_salary_coach(job_posting: str, resume: str = "") -> AsyncIterator[dict[str, Any]]:
    """Stream the salary prompt and the model's response text."""
    from app.agents.research import _build_sources_section
    async for event in iter_text_query(
        prompt=build_salary_prompt(job_posting, resume),
        options=build_salary_options(),
        trace_name="salary-coach",
    ):
        if event.get("type") == "complete":
            sources = _build_sources_section(event.get("tool_uses", []))
            text = event.get("text", "")
            if sources:
                text = text.rstrip() + "\n\n" + sources
            yield {**event, "text": text}
        else:
            yield event


CONCERNS_PROMPT = load_prompt("concerns")
CONCERNS_SYSTEM_PROMPT = load_system_prompt("concerns")


@traced_agent("anticipate-concerns", tags=["interview-prep"])
async def anticipate_concerns(job_posting: str, resume: str) -> str:
    """Anticipate interviewer concerns with counter-evidence."""
    analysis = ""
    async for event in stream_anticipate_concerns(job_posting, resume):
        if event.get("type") == "complete":
            analysis = event.get("text", "")
    return analysis


def build_concerns_prompt(job_posting: str, resume: str) -> str:
    """Build the interviewer concerns prompt."""
    return CONCERNS_PROMPT.format(job_posting=job_posting, resume=resume)


def build_concerns_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for interviewer concerns."""
    return ClaudeAgentOptions(
        system_prompt=CONCERNS_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=5,
        allowed_tools=[],
    )


async def stream_anticipate_concerns(job_posting: str, resume: str) -> AsyncIterator[dict[str, Any]]:
    """Stream the concerns prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_concerns_prompt(job_posting, resume),
        options=build_concerns_options(),
        trace_name="anticipate-concerns",
    ):
        yield event


INTERVIEW_INTEL_PROMPT = load_prompt("interview_intel")
INTERVIEW_INTEL_SYSTEM_PROMPT = load_system_prompt("interview_intel")


def _is_technical_role(position: str) -> bool:
    """Heuristic: treat role as technical if the position title mentions coding, engineering, or similar signals."""
    technical_keywords = [
        "engineer", "developer", "programmer", "software", "coding", "swe",
        "backend", "frontend", "fullstack", "full-stack", "full stack",
        "data scientist", "data engineer", "ml engineer", "machine learning",
        "devops", "sre",
    ]
    lower = position.lower()
    return any(kw in lower for kw in technical_keywords)


TECHNICAL_SECTION_TEMPLATE = load_prompt("interview_intel_technical")

NONTECHNICAL_SECTION = ""


def build_interview_intel_prompt(company_name: str, job_posting: str, position: str = "") -> str:
    """Build the interview intel prompt, injecting a technical section when appropriate."""
    if _is_technical_role(position):
        technical_section = TECHNICAL_SECTION_TEMPLATE.format(company_name=company_name)
    else:
        technical_section = NONTECHNICAL_SECTION
    return INTERVIEW_INTEL_PROMPT.format(
        company_name=company_name,
        job_posting=job_posting,
        technical_section=technical_section,
    )


def build_interview_intel_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for interview intel."""
    return ClaudeAgentOptions(
        system_prompt=INTERVIEW_INTEL_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        max_turns=30,  # needs multiple search iterations to cover all sections
        allowed_tools=["WebSearch", "WebFetch"],
    )


async def stream_interview_intel(company_name: str, job_posting: str, position: str = "") -> AsyncIterator[dict[str, Any]]:
    """Stream the interview intel prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_interview_intel_prompt(company_name, job_posting, position),
        options=build_interview_intel_options(),
        trace_name="interview-intel",
    ):
        yield event


@traced_agent("interview-intel", tags=["web-search", "interview-prep"])
async def run_interview_intel(company_name: str, job_posting: str, position: str = "") -> str:
    """Mine the web for interview questions and process details. Returns report text."""
    report = ""
    async for event in stream_interview_intel(company_name, job_posting, position):
        if event.get("type") == "complete":
            report = event.get("text", "")
    return report


PITCH_PROMPT = load_prompt("pitch")
PITCH_SYSTEM_PROMPT = load_system_prompt("pitch")


@traced_agent("build-pitches", tags=["pitch", "positioning"])
async def build_pitches(job_posting: str, resume: str) -> str:
    """Build multi-format pitch variants."""
    pitches = ""
    async for event in stream_build_pitches(job_posting, resume):
        if event.get("type") == "complete":
            pitches = event.get("text", "")
    return pitches


def build_pitch_prompt(job_posting: str, resume: str) -> str:
    """Build the pitch-generation prompt."""
    return PITCH_PROMPT.format(job_posting=job_posting, resume=resume)


def build_pitch_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for pitch generation."""
    return ClaudeAgentOptions(
        system_prompt=PITCH_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=5,
        allowed_tools=[],
    )


async def stream_build_pitches(job_posting: str, resume: str) -> AsyncIterator[dict[str, Any]]:
    """Stream the pitch prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_pitch_prompt(job_posting, resume),
        options=build_pitch_options(),
        trace_name="build-pitches",
    ):
        yield event
