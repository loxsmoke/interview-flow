"""Resume Chat Agent — interactive multi-turn conversation for resume tailoring."""

from __future__ import annotations

import logging

from app.agents.streaming import get_active_provider, get_temperature

_TEMPERATURE = get_temperature("resume-chat")
from app.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


RESUME_CHAT_SYSTEM = load_prompt("resume_chat")

_OPENING_MESSAGE = (
    "I'd like to work on tailoring my resume for this role. "
    "Give me a brief summary of the top 3 changes that would have the most impact, "
    "then ask me which area I'd like to start with."
)


class ResumeChatSession:
    """Manages a multi-turn resume coaching conversation."""

    def __init__(self, job_posting: str, resume: str, review: str = ""):
        self.job_posting = job_posting
        self.resume = resume
        self.review = review
        self.history: list[dict] = []
        self.is_started = False
        self._messages: list[dict] = []
        self._provider: str = ""

    def _build_system(self) -> str:
        review_section = f"### Previous AI Analysis\n{self.review}" if self.review else ""
        return RESUME_CHAT_SYSTEM.format(
            job_posting=self.job_posting,
            resume=self.resume,
            review_section=review_section,
        )

    async def start(self) -> str:
        """Start the chat session. Returns the coach's opening message."""
        system = self._build_system()
        self._provider = get_active_provider()
        self._messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": _OPENING_MESSAGE},
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
        """Send user message and get the coach's response."""
        if not self.is_started:
            raise RuntimeError("Chat session not started")
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
        return response

    async def _openai_turn(self) -> str:
        import asyncio, openai, os
        from app.agents.streaming import _parse_retry_after
        model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
        client = openai.AsyncOpenAI()
        for _attempt in range(2):
            try:
                resp = await client.chat.completions.create(model=model, messages=self._messages, temperature=_TEMPERATURE)
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
        import os
        from app.agents.streaming import ollama_chat_once
        model = os.environ.get("OLLAMA_MODEL", "llama3.2").strip() or "llama3.2"
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
        return await ollama_chat_once(self._messages, model, base_url, _TEMPERATURE)

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
        """Clean up the session."""
        self._messages = []
