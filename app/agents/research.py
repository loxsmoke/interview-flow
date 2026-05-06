"""Company Research Agent — deep-dives into a company using web search."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions
from app.agents.streaming import iter_text_query
from app.prompt_loader import load_prompt, load_system_prompt
from app.tracing import traced_agent

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = load_prompt("research")
RESEARCH_SYSTEM_PROMPT = load_system_prompt("research")


def build_research_prompt(job_posting: str, resume: str = "") -> str:
    """Build the company research prompt."""
    resume_section = (
        f"## Candidate Resume (for fit assessment)\n<user_provided_resume>\n{resume}\n</user_provided_resume>"
        if resume
        else ""
    )
    return RESEARCH_PROMPT.format(job_posting=job_posting, resume_section=resume_section)


def build_research_options() -> ClaudeAgentOptions:
    """Return the Claude agent options for company research."""
    return ClaudeAgentOptions(
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",  # server-side agent — no interactive user to approve tool calls
        max_turns=30,  # research needs many search iterations to cover 5 dimensions thoroughly
        allowed_tools=["WebSearch", "WebFetch"],  # web access for real-time company data
    )


def _build_sources_section(tool_uses: list[dict]) -> str:
    """Build a markdown Sources section from collected tool use events."""
    seen_urls: list[dict] = []
    seen_url_set: set[str] = set()
    seen_queries: list[str] = []
    seen_query_set: set[str] = set()

    for tu in tool_uses:
        tool = tu.get("tool", "")
        inp = tu.get("input", {}) or {}
        if tool == "WebFetch":
            url = inp.get("url", "").strip()
            title = inp.get("title", "").strip()
            if url and url not in seen_url_set:
                seen_url_set.add(url)
                seen_urls.append({"url": url, "title": title})
        elif tool == "WebSearch":
            q = inp.get("query", "").strip()
            if q and q not in seen_query_set:
                seen_query_set.add(q)
                seen_queries.append(q)

    if not seen_urls and not seen_queries:
        return ""

    lines = ["---", "## Sources"]
    if seen_urls:
        for item in seen_urls:
            url = item["url"]
            label = item["title"] if item["title"] else url
            lines.append(f"- [{label}]({url})")
    if seen_queries:
        if seen_urls:
            lines.append("")
        lines.append("**Search queries used:**")
        for q in seen_queries:
            lines.append(f"- {q}")

    return "\n".join(lines)


async def stream_research(job_posting: str, resume: str = "") -> AsyncIterator[dict[str, Any]]:
    """Stream the research prompt and the model's response text."""
    async for event in iter_text_query(
        prompt=build_research_prompt(job_posting, resume),
        options=build_research_options(),
        trace_name="company-research",
    ):
        if event.get("type") == "complete":
            sources = _build_sources_section(event.get("tool_uses", []))
            text = event.get("text", "")
            if sources:
                text = text.rstrip() + "\n\n" + sources
            yield {**event, "text": text}
        else:
            yield event


@traced_agent("research", tags=["web-search", "company-analysis"])
async def run_research(job_posting: str, resume: str = "") -> dict:
    """Run company research agent. Returns structured research results."""
    report = ""
    cost = 0.0
    model_name = ""
    duration_ms = 0
    async for event in stream_research(job_posting, resume):
        if event.get("type") == "complete":
            report = event.get("text", "")
            cost = event.get("cost_usd", 0.0) or 0.0
            model_name = event.get("model_name", "") or ""
            duration_ms = event.get("duration_ms", 0) or 0

    return {
        "raw_report": report,
        "cost_usd": cost,
        "model_name": model_name,
        "duration_ms": duration_ms,
    }
