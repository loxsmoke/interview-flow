"""Mock Interview Agent — runs realistic interview simulations with scoring."""

from __future__ import annotations

import logging

from app.agents.streaming import get_active_provider, get_temperature

_TEMPERATURE = get_temperature("mock-interview")
from app.prompt_loader import load_prompt
from app.tracing import trace_agent

logger = logging.getLogger(__name__)

MOCK_SYSTEM_PROMPT = load_prompt("mock_interview")

FORMAT_INSTRUCTIONS = {
    "behavioral": "Focus on behavioral questions (Tell me about a time when...). Probe for STAR structure. Test leadership, conflict resolution, ambiguity, failure, and impact.",
    "system_design": "Present a system design problem relevant to the company's products. Evaluate: scoping, API design, high-level architecture, data model, scalability, tradeoffs. Push back on initial designs. When illustrating architecture or data flows, use Mermaid diagrams (```mermaid code blocks) — never ASCII art.",
    "case_study": "Present a product/business case relevant to the company. Evaluate: problem framing, structure, creativity, data-driven thinking, prioritization, communication.",
    "panel": "Simulate a panel with 2-3 interviewers (give each a name and role). Each asks questions from their perspective. Test how the candidate handles different communication styles.",
    "bar_raiser": "Channel Amazon's bar raiser style — deeply behavioral, principle-focused, with rigorous follow-ups. Push until the candidate either demonstrates depth or runs out of substance.",
}


class MockInterviewSession:
    """Manages a multi-turn mock interview conversation."""

    def __init__(self, company_name: str, job_posting: str, resume: str, stories: str, interview_format: str = "behavioral"):
        self.company_name = company_name
        self.job_posting = job_posting
        self.resume = resume
        self.stories = stories
        self.interview_format = interview_format
        self.history: list[dict] = []
        self.is_started = False
        self.is_complete = False
        self._trace = None
        self._messages: list[dict] = []
        self._provider: str = ""

    def _build_system(self) -> str:
        format_inst = FORMAT_INSTRUCTIONS.get(self.interview_format, FORMAT_INSTRUCTIONS["behavioral"])
        return MOCK_SYSTEM_PROMPT.format(
            company_name=self.company_name or "the company",
            format=self.interview_format,
            job_posting=self.job_posting,
            resume=self.resume or "Not provided",
            stories=self.stories or "No stories in bank yet.",
            format_instructions=format_inst,
        )

    async def start(self) -> str:
        """Start the interview. Returns the interviewer's opening."""
        system = self._build_system()
        self._provider = get_active_provider()

        from app.tracing import _get_langfuse
        lf = _get_langfuse()
        if lf:
            try:
                self._trace = lf.trace(
                    name=f"interview-flow/mock-interview-{self.interview_format}",
                    metadata={"company": self.company_name, "format": self.interview_format},
                    tags=["mock-interview", self.interview_format],
                )
            except Exception:
                logger.warning("Failed to create mock interview trace", exc_info=True)

        self._messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "Begin the interview."},
        ]
        if self._provider == "openai":
            response = await self._openai_turn()
        elif self._provider == "ollama":
            response = await self._ollama_turn()
        else:
            response = await self._anthropic_turn()
        self._messages.append({"role": "assistant", "content": response})

        self.is_started = True
        self.history.append({"role": "assistant", "content": response})
        return response

    async def respond(self, user_message: str) -> str:
        """Send candidate's response and get interviewer's next turn."""
        if not self.is_started:
            raise RuntimeError("Interview not started")

        self.history.append({"role": "user", "content": user_message})

        self._messages.append({"role": "user", "content": user_message})
        if self._provider == "openai":
            response = await self._openai_turn()
        elif self._provider == "ollama":
            response = await self._ollama_turn()
        else:
            response = await self._anthropic_turn()
        self._messages.append({"role": "assistant", "content": response})

        self.history.append({"role": "assistant", "content": response})
        if "END_OF_INTERVIEW" in response:
            self.is_complete = True
        return response

    async def _openai_turn(self) -> str:
        import asyncio, openai, os
        from app.agents.streaming import _parse_retry_after
        model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
        client = openai.AsyncOpenAI()
        for _attempt in range(2):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=self._messages,
                    temperature=_TEMPERATURE,
                )
                return resp.choices[0].message.content or ""
            except openai.RateLimitError as _exc:
                if _attempt == 1:
                    raise
                _wait = _parse_retry_after(str(_exc))
                if _wait is None:
                    raise
                logger.warning("OpenAI rate limit hit, retrying after %.1fs (suggested %.1fs) — non-streaming, safe to retry", _wait * 2, _wait)
                await asyncio.sleep(_wait * 2)
        return ""  # unreachable

    async def _ollama_turn(self) -> str:
        import openai, os
        model = os.environ.get("OLLAMA_MODEL", "llama3.2").strip() or "llama3.2"
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
        client = openai.AsyncOpenAI(base_url=f"{base_url.rstrip('/')}/v1", api_key="ollama")
        resp = await client.chat.completions.create(model=model, messages=self._messages, temperature=_TEMPERATURE)
        return resp.choices[0].message.content or ""

    async def _anthropic_turn(self) -> str:
        import anthropic, os
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
        client = anthropic.AsyncAnthropic()
        system = next((m["content"] for m in self._messages if m["role"] == "system"), "")
        messages = [m for m in self._messages if m["role"] != "system"]
        kwargs: dict = dict(model=model, max_tokens=8192, temperature=_TEMPERATURE, messages=messages)
        if system:
            kwargs["system"] = system
        resp = await client.messages.create(**kwargs)
        return resp.content[0].text if resp.content else ""

    async def close(self):
        """Clean up the session and finalize the Langfuse trace."""
        if self._trace:
            try:
                self._trace.update(
                    output=f"Completed: {len(self.history)} turns, format={self.interview_format}",
                    metadata={"turns": len(self.history), "completed": self.is_complete},
                )
                from app.tracing import _get_langfuse
                lf = _get_langfuse()
                if lf:
                    lf.flush()
            except Exception:
                pass
            self._trace = None
        self._messages = []
