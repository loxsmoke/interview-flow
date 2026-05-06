"""Helpers for streaming agent prompts and responses to the frontend."""

from __future__ import annotations

import json as _json
import logging
import os
import time
from typing import Any, AsyncIterator

_lf_log = logging.getLogger("langfuse.streaming")

from claude_agent_sdk import ClaudeAgentOptions


def _parse_retry_after(message: str) -> float | None:
    """Extract the suggested wait time in seconds from an OpenAI rate-limit error message.

    Handles formats like 'try again in 1.5s', 'try again in 800ms', 'try again in 1m30s'.
    Returns None when no wait time is found (caller should not retry).
    """
    import re
    m = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)\b', message, re.IGNORECASE)
    if m:
        val, unit = float(m.group(1)), m.group(2).lower()
        return val / 1000 if unit == 'ms' else val
    m = re.search(r'try again in (?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?', message, re.IGNORECASE)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return None


async def _wait_with_heartbeats(seconds: float) -> AsyncIterator[dict[str, Any]]:
    """Sleep for `seconds`, yielding a heartbeat event every 5 s to keep the SSE connection alive."""
    import asyncio
    import math
    elapsed = 0.0
    while elapsed < seconds:
        chunk = min(5.0, seconds - elapsed)
        await asyncio.sleep(chunk)
        elapsed += chunk
        remaining = max(0.0, seconds - elapsed)
        yield {"type": "rate_limit_retry", "remaining_seconds": math.ceil(remaining)}


def _parse_anthropic_retry_after(exc) -> float:
    """Extract retry-after seconds from an Anthropic rate-limit error.

    Reads the Retry-After response header when available; falls back to 60s
    (one full minute — the token-bucket window for Anthropic per-minute limits).
    """
    try:
        headers = exc.response.headers
        val = headers.get("retry-after") or headers.get("Retry-After")
        if val:
            return float(val)
    except Exception:
        pass
    return 60.0

# ── Provider selection ───────────────────────────────────────────────────────

def get_active_provider() -> str:
    """Return 'anthropic', 'openai', or 'ollama' based on env configuration."""
    explicit = os.environ.get("ACTIVE_PROVIDER", "").strip().lower()
    if explicit in ("anthropic", "openai", "ollama"):
        return explicit
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai"
    return "anthropic"


# ── OpenAI cost calculation ──────────────────────────────────────────────────

# (input_per_million_tokens, output_per_million_tokens) in USD
_OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.5":      ( 5.00, 30.00),
    "gpt-5.5-pro":  (30.00,180.00),
    "gpt-5.4":      ( 5.00, 20.00),
    "gpt-5.4-mini": ( 0.75,  3.00),
    "gpt-5":        ( 5.00, 20.00),
    "gpt-5-mini":   ( 0.75,  3.00),
    "gpt-4.1":      ( 2.00,  8.00),
    "gpt-4.1-mini": ( 0.40,  1.60),
    "gpt-4o":       ( 2.50, 10.00),
    "gpt-4o-mini":  ( 0.15,  0.60),
}
_OPENAI_DEFAULT_PRICING = (2.50, 10.00)

_WEB_TOOLS = {"WebSearch", "WebFetch"}

# ── Anthropic cost calculation ────────────────────────────────────────────────

_ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":           (15.00, 75.00),
    "claude-sonnet-4-6":         ( 3.00, 15.00),
    "claude-haiku-4-5-20251001": ( 0.80,  4.00),
}
_ANTHROPIC_DEFAULT_PRICING = (3.00, 15.00)


def _anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = _ANTHROPIC_PRICING.get(model, _ANTHROPIC_DEFAULT_PRICING)
    return (input_tokens * inp + output_tokens * out) / 1_000_000


def _openai_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = _OPENAI_PRICING.get(model, _OPENAI_DEFAULT_PRICING)
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000


# ── OpenAI: chat completions (no web search) ─────────────────────────────────

async def _iter_openai_chat(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import openai
    client = openai.AsyncOpenAI()
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    full_text: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    actual_model = model
    t0 = time.monotonic()

    import asyncio
    _MAX_ATTEMPTS = 5
    for _attempt in range(_MAX_ATTEMPTS):
        full_text = []
        prompt_tokens = 0
        completion_tokens = 0
        actual_model = model
        t0 = time.monotonic()
        received_any = False
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        full_text.append(delta)
                        received_any = True
                        yield {"type": "receive", "text": delta}
                if chunk.model:
                    actual_model = chunk.model
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
            break  # success
        except openai.RateLimitError as _exc:
            if _attempt == _MAX_ATTEMPTS - 1:
                raise
            _suggested = _parse_retry_after(str(_exc))
            _wait = max(_suggested or 60.0, 60.0) if received_any else (_suggested or 10.0)
            print(f"[OpenAI] rate limit hit ({'mid' if received_any else 'pre'}-stream, attempt {_attempt + 1}/{_MAX_ATTEMPTS - 1}), retrying after {_wait:.1f}s ...", flush=True)
            async for hb in _wait_with_heartbeats(_wait):
                yield hb
            if received_any:
                yield {"type": "rate_limit_reset"}

    duration_ms = int((time.monotonic() - t0) * 1000)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": _openai_cost(actual_model, prompt_tokens, completion_tokens),
        "model_name": actual_model,
        "duration_ms": duration_ms,
        "tool_uses": [],
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
    }


# ── OpenAI: Responses API with web_search_preview ────────────────────────────

async def _iter_openai_responses_impl(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import openai
    client = openai.AsyncOpenAI()

    input_messages: list[dict] = []
    if system:
        input_messages.append({"role": "developer", "content": system})
    input_messages.append({"role": "user", "content": prompt})

    full_text: list[str] = []
    tool_uses: list[dict] = []
    t0 = time.monotonic()
    actual_model = model
    prompt_tokens = 0
    completion_tokens = 0

    async with client.responses.stream(
        model=model,
        tools=[{"type": "web_search_preview"}],
        input=input_messages,
    ) as stream:
        async for event in stream:
            event_type = getattr(event, "type", "")

            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if item and getattr(item, "type", "") == "web_search_call":
                    q = getattr(item, "query", "") or ""
                    if q:
                        entry = {"tool": "WebSearch", "input": {"query": q}}
                        tool_uses.append(entry)
                        yield {"type": "tool_use", **entry}

            elif event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    full_text.append(delta)
                    yield {"type": "receive", "text": delta}

        final = await stream.get_final_response()

    actual_model = getattr(final, "model", model) or model
    usage = getattr(final, "usage", None)
    if usage:
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0

    # Extract citation URLs from the completed response
    for item in getattr(final, "output", []):
        if getattr(item, "type", "") == "message":
            for content_block in getattr(item, "content", []):
                for annotation in getattr(content_block, "annotations", []):
                    if getattr(annotation, "type", "") == "url_citation":
                        url = getattr(annotation, "url", "") or ""
                        title = getattr(annotation, "title", "") or ""
                        if url:
                            entry = {"tool": "WebFetch", "input": {"url": url, "title": title}}
                            if not any(e["input"].get("url") == url for e in tool_uses):
                                tool_uses.append(entry)
                                yield {"type": "tool_use", **entry}

    duration_ms = int((time.monotonic() - t0) * 1000)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": _openai_cost(actual_model, prompt_tokens, completion_tokens),
        "model_name": actual_model,
        "duration_ms": duration_ms,
        "tool_uses": tool_uses,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
    }


async def _iter_openai_responses(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import asyncio
    import openai
    _MAX_ATTEMPTS = 5
    for _attempt in range(_MAX_ATTEMPTS):
        received_any = False
        try:
            async for event in _iter_openai_responses_impl(prompt, system, model):
                if event.get("type") in ("receive", "tool_use"):
                    received_any = True
                yield event
            return
        except openai.RateLimitError as _exc:
            if _attempt == _MAX_ATTEMPTS - 1:
                raise
            _suggested = _parse_retry_after(str(_exc))
            _wait = max(_suggested or 60.0, 60.0) if received_any else (_suggested or 10.0)
            print(f"[OpenAI] rate limit hit ({'mid' if received_any else 'pre'}-stream, attempt {_attempt + 1}/{_MAX_ATTEMPTS - 1}), retrying after {_wait:.1f}s ...", flush=True)
            async for hb in _wait_with_heartbeats(_wait):
                yield hb
            if received_any:
                yield {"type": "rate_limit_reset"}


# ── DuckDuckGo search helpers ─────────────────────────────────────────────────

async def _search_duckduckgo(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search in a thread and return formatted results."""
    import asyncio
    from ddgs import DDGS

    def _sync() -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    try:
        results = await asyncio.to_thread(_sync)
    except Exception as exc:
        return f"Web search failed for '{query}': {exc}"

    if not results:
        return f"No results found for query: {query}"

    lines = [f"Search results for '{query}':", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   URL: {r.get('href', '')}")
        lines.append(f"   {r.get('body', '')}")
        lines.append("")
    return "\n".join(lines)


async def _fetch_url(url: str, timeout: float = 15.0) -> str:
    """Fetch a URL and return its stripped text content (capped at 8 000 chars)."""
    import re
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; interview-flow/1.0)"},
            )
            text = resp.text
    except Exception as exc:
        return f"Failed to fetch {url}: {exc}"

    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]


# ── Ollama: OpenAI-compatible chat completions ───────────────────────────────

async def _iter_ollama_chat(
    prompt: str, system: str, model: str, base_url: str
) -> AsyncIterator[dict[str, Any]]:
    import openai
    client = openai.AsyncOpenAI(
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key="ollama",  # Ollama ignores the key but the SDK requires a non-empty value
    )
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    full_text: list[str] = []
    t0 = time.monotonic()

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    chunk_count = 0
    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text.append(delta)
                chunk_count += 1
                yield {"type": "receive", "text": delta}

    print(f"[Ollama] stream loop done: {chunk_count} chunks, {len(full_text)} parts", flush=True)
    duration_ms = int((time.monotonic() - t0) * 1000)
    print("[Ollama] yielding complete event", flush=True)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": 0.0,
        "model_name": model,
        "duration_ms": duration_ms,
        "tool_uses": [],
    }
    print("[Ollama] complete event yielded", flush=True)


def _search_status(done: int, failed: int, empty: int) -> str:
    """Classify the outcome of all web searches in a run."""
    if done == 0:
        return "not_searched"
    successful = done - failed - empty
    if successful > 0:
        return "ok"
    if failed > 0:
        return "connection_error"
    return "no_results"


# ── Ollama: tool-calling loop with DuckDuckGo web search ─────────────────────

_OLLAMA_WEB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information such as company details, salary data, interview experiences, and news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and read the text content of a webpage URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
]


async def _iter_ollama_web(
    prompt: str, system: str, model: str, base_url: str
) -> AsyncIterator[dict[str, Any]]:
    import openai

    client = openai.AsyncOpenAI(
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key="ollama",
    )
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    all_tool_uses: list[dict] = []
    full_text: list[str] = []
    searches_done = 0
    searches_failed = 0   # network / API errors
    searches_empty = 0    # query ran but returned no results
    t0 = time.monotonic()

    for _turn in range(15):
        content_parts: list[str] = []
        pending: dict[int, dict] = {}  # index -> {id, name, args_parts}

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_OLLAMA_WEB_TOOLS,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                content_parts.append(delta.content)
                full_text.append(delta.content)
                yield {"type": "receive", "text": delta.content}

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending:
                        pending[idx] = {"id": "", "name": "", "args_parts": []}
                    if tc_delta.id:
                        pending[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            pending[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            pending[idx]["args_parts"].append(tc_delta.function.arguments)

        if not pending:
            break  # no tool calls — final answer done

        # Append assistant turn with tool calls to history
        messages.append({
            "role": "assistant",
            "content": "".join(content_parts),
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": "".join(tc["args_parts"])},
                }
                for tc in pending.values()
            ],
        })

        # Execute each tool and inject results
        for tc in pending.values():
            fn_name = tc["name"]
            try:
                fn_args = _json.loads("".join(tc["args_parts"]))
            except Exception:
                fn_args = {}

            if fn_name == "web_search":
                query = fn_args.get("query", "")
                entry = {"tool": "WebSearch", "input": {"query": query}}
                all_tool_uses.append(entry)
                yield {"type": "tool_use", **entry}
                result = await _search_duckduckgo(query)
                searches_done += 1
                if result.startswith("Web search failed"):
                    searches_failed += 1
                elif result.startswith("No results found"):
                    searches_empty += 1
            elif fn_name == "fetch_url":
                url = fn_args.get("url", "")
                entry = {"tool": "WebFetch", "input": {"url": url}}
                all_tool_uses.append(entry)
                yield {"type": "tool_use", **entry}
                result = await _fetch_url(url)
            else:
                result = f"Unknown tool: {fn_name}"

            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    duration_ms = int((time.monotonic() - t0) * 1000)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": 0.0,
        "model_name": model,
        "duration_ms": duration_ms,
        "tool_uses": all_tool_uses,
        "search_status": _search_status(searches_done, searches_failed, searches_empty),
    }


# ── Anthropic: direct Messages API (no web search) ───────────────────────────

async def _iter_anthropic_chat_impl(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import anthropic
    client = anthropic.AsyncAnthropic()
    kwargs: dict = dict(model=model, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
    if system:
        kwargs["system"] = system

    full_text: list[str] = []
    input_tokens = 0
    output_tokens = 0
    actual_model = model
    t0 = time.monotonic()

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            etype = getattr(event, "type", "")
            if etype == "message_start":
                msg = getattr(event, "message", None)
                if msg:
                    actual_model = getattr(msg, "model", model) or model
                    usage = getattr(msg, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "input_tokens", 0) or 0
            elif etype == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta and getattr(delta, "type", "") == "text_delta":
                    text = getattr(delta, "text", "") or ""
                    if text:
                        full_text.append(text)
                        yield {"type": "receive", "text": text}
            elif etype == "message_delta":
                usage = getattr(event, "usage", None)
                if usage:
                    output_tokens = getattr(usage, "output_tokens", 0) or 0

    duration_ms = int((time.monotonic() - t0) * 1000)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": _anthropic_cost(actual_model, input_tokens, output_tokens),
        "model_name": actual_model,
        "duration_ms": duration_ms,
        "tool_uses": [],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _iter_anthropic_chat(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import asyncio
    import anthropic
    _MAX_ATTEMPTS = 5
    for _attempt in range(_MAX_ATTEMPTS):
        received_any = False
        try:
            async for event in _iter_anthropic_chat_impl(prompt, system, model):
                if event.get("type") == "receive":
                    received_any = True
                yield event
            return
        except anthropic.RateLimitError as _exc:
            if _attempt == _MAX_ATTEMPTS - 1:
                raise
            _suggested = _parse_anthropic_retry_after(_exc)
            _wait = max(_suggested, 60.0) if received_any else _suggested
            print(f"[Anthropic] rate limit hit ({'mid' if received_any else 'pre'}-stream, attempt {_attempt + 1}/{_MAX_ATTEMPTS - 1}), retrying after {_wait:.1f}s ...", flush=True)
            async for hb in _wait_with_heartbeats(_wait):
                yield hb
            if received_any:
                yield {"type": "rate_limit_reset"}


# ── Anthropic: direct Messages API with web_search tool ──────────────────────

async def _iter_anthropic_web_impl(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import anthropic
    client = anthropic.AsyncAnthropic()
    kwargs: dict = dict(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )
    if system:
        kwargs["system"] = system

    full_text: list[str] = []
    tool_uses: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    actual_model = model
    t0 = time.monotonic()
    current_tool_name = ""
    current_tool_parts: list[str] = []

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            etype = getattr(event, "type", "")

            if etype == "message_start":
                msg = getattr(event, "message", None)
                if msg:
                    actual_model = getattr(msg, "model", model) or model
                    usage = getattr(msg, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "input_tokens", 0) or 0

            elif etype == "content_block_start":
                block = getattr(event, "content_block", None)
                if block and getattr(block, "type", "") == "tool_use":
                    current_tool_name = getattr(block, "name", "") or ""
                    current_tool_parts = []

            elif etype == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta:
                    dtype = getattr(delta, "type", "")
                    if dtype == "text_delta":
                        text = getattr(delta, "text", "") or ""
                        if text:
                            full_text.append(text)
                            yield {"type": "receive", "text": text}
                    elif dtype == "input_json_delta":
                        current_tool_parts.append(getattr(delta, "partial_json", "") or "")

            elif etype == "content_block_stop":
                if current_tool_name == "web_search" and current_tool_parts:
                    try:
                        inp = _json.loads("".join(current_tool_parts))
                        q = inp.get("query", "")
                        if q:
                            entry = {"tool": "WebSearch", "input": {"query": q}}
                            tool_uses.append(entry)
                            yield {"type": "tool_use", **entry}
                    except Exception:
                        pass
                current_tool_name = ""
                current_tool_parts = []

            elif etype == "message_delta":
                usage = getattr(event, "usage", None)
                if usage:
                    output_tokens = getattr(usage, "output_tokens", 0) or 0

    duration_ms = int((time.monotonic() - t0) * 1000)
    yield {
        "type": "complete",
        "text": "".join(full_text),
        "cost_usd": _anthropic_cost(actual_model, input_tokens, output_tokens),
        "model_name": actual_model,
        "duration_ms": duration_ms,
        "tool_uses": tool_uses,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _iter_anthropic_web(
    prompt: str, system: str, model: str
) -> AsyncIterator[dict[str, Any]]:
    import asyncio
    import anthropic
    _MAX_ATTEMPTS = 5
    for _attempt in range(_MAX_ATTEMPTS):
        received_any = False
        try:
            async for event in _iter_anthropic_web_impl(prompt, system, model):
                if event.get("type") in ("receive", "tool_use"):
                    received_any = True
                yield event
            return
        except anthropic.RateLimitError as _exc:
            if _attempt == _MAX_ATTEMPTS - 1:
                raise
            _suggested = _parse_anthropic_retry_after(_exc)
            _wait = max(_suggested, 60.0) if received_any else _suggested
            print(f"[Anthropic] rate limit hit ({'mid' if received_any else 'pre'}-stream, attempt {_attempt + 1}/{_MAX_ATTEMPTS - 1}), retrying after {_wait:.1f}s ...", flush=True)
            async for hb in _wait_with_heartbeats(_wait):
                yield hb
            if received_any:
                yield {"type": "rate_limit_reset"}


# ── Langfuse generation tracking ─────────────────────────────────────────────

def _lf_start(name: str, provider: str, model: str, system: str, prompt: str):
    """Open a Langfuse generation span. Returns the generation object or None."""
    try:
        from app.tracing import get_langfuse
        lf = get_langfuse()
        if not lf:
            print("[Langfuse] not configured - skipping", flush=True)
            return None
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        gen = lf.start_observation(
            name=name,
            as_type="generation",
            model=model,
            model_parameters={"provider": provider},
            input=messages,
        )
        print(f"[Langfuse] generation started: {name} ({provider} / {model})", flush=True)
        return gen
    except Exception as exc:
        import traceback
        print(f"[Langfuse] _lf_start failed: {exc}", flush=True)
        traceback.print_exc()
        return None


def _lf_end(gen, event: dict) -> None:
    """Close a Langfuse generation with data from the complete event."""
    print(f"[Langfuse] _lf_end entered, gen={gen is not None}", flush=True)
    if not gen:
        return
    try:
        input_tokens = event.get("input_tokens", 0) or 0
        output_tokens = event.get("output_tokens", 0) or 0
        update_kwargs: dict = dict(
            output=event.get("text", ""),
            model=event.get("model_name") or None,
            metadata={
                "cost_usd": event.get("cost_usd", 0.0),
                "duration_ms": event.get("duration_ms", 0),
                "tool_calls": event.get("tool_uses", []),
            },
        )
        if input_tokens or output_tokens:
            update_kwargs["usage_details"] = {"input": input_tokens, "output": output_tokens}
        cost_usd = event.get("cost_usd") or 0.0
        if cost_usd:
            update_kwargs["cost_details"] = {"total": cost_usd}
        gen.update(**update_kwargs)
        gen.end()
        print("[Langfuse] generation ended, flushing...", flush=True)
        from app.tracing import get_langfuse
        lf = get_langfuse()
        if lf:
            lf.flush()
        print("[Langfuse] flush done", flush=True)
    except Exception as exc:
        import traceback
        print(f"[Langfuse] _lf_end failed: {exc}", flush=True)
        traceback.print_exc()


def _lf_fail(gen, exc: Exception) -> None:
    """Mark a Langfuse generation as failed."""
    if not gen:
        return
    try:
        gen.update(level="ERROR", status_message=str(exc))
        gen.end()
        from app.tracing import get_langfuse
        lf = get_langfuse()
        if lf:
            lf.flush()
    except Exception:
        _lf_log.warning("Failed to mark Langfuse generation as failed", exc_info=True)


# ── Main entry point ─────────────────────────────────────────────────────────

async def iter_text_query(
    prompt: str,
    options: ClaudeAgentOptions,
    trace_name: str = "query",
) -> AsyncIterator[dict[str, Any]]:
    """Yield request/response events for a text-producing query.

    Routes to the active AI provider (Anthropic, OpenAI, or Ollama) based on
    ACTIVE_PROVIDER. Emits events: send, tool_use, receive, complete.
    Each call is recorded as a Langfuse generation when Langfuse is configured.
    """
    system_text = getattr(options, "system_prompt", "") or ""
    if not isinstance(system_text, str):
        system_text = ""

    yield {"type": "send", "channel": "system", "text": system_text}
    yield {"type": "send", "channel": "user", "text": prompt}

    provider = get_active_provider()
    uses_web = bool(set(getattr(options, "allowed_tools", []) or []) & _WEB_TOOLS)

    if provider == "ollama":
        model = os.environ.get("OLLAMA_MODEL", "llama3.2").strip() or "llama3.2"
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
        gen = _lf_start(trace_name, provider, model, system_text, prompt)
        complete_event: dict | None = None
        _stream_exc: Exception | None = None
        try:
            src = _iter_ollama_web(prompt, system_text, model, base_url) if uses_web else _iter_ollama_chat(prompt, system_text, model, base_url)
            async for event in src:
                etype = event.get("type")
                print(f"[Langfuse] event: {etype}", flush=True)
                if etype == "complete":
                    complete_event = event
                yield event
        except Exception as exc:
            print(f"[Langfuse] exception in ollama stream: {exc}", flush=True)
            import traceback; traceback.print_exc()
            _stream_exc = exc
            raise
        finally:
            print(f"[Langfuse] ollama finally: complete={'present' if complete_event else 'MISSING'}, exc={_stream_exc is not None}", flush=True)
            if _stream_exc is not None:
                _lf_fail(gen, _stream_exc)
            elif complete_event is not None:
                _lf_end(gen, complete_event)
            else:
                _lf_fail(gen, RuntimeError("stream closed before complete event"))
        return

    if provider == "openai":
        model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
        gen = _lf_start(trace_name, provider, model, system_text, prompt)
        complete_event = None
        _stream_exc = None
        try:
            src = _iter_openai_responses(prompt, system_text, model) if uses_web else _iter_openai_chat(prompt, system_text, model)
            async for event in src:
                if event.get("type") == "complete":
                    complete_event = event
                yield event
        except Exception as exc:
            _stream_exc = exc
            raise
        finally:
            if _stream_exc is not None:
                _lf_fail(gen, _stream_exc)
            elif complete_event is not None:
                _lf_end(gen, complete_event)
            else:
                _lf_fail(gen, RuntimeError("stream closed before complete event"))
        return

    # ── Anthropic direct API ─────────────────────────────────────────────────
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
    gen = _lf_start(trace_name, provider, model, system_text, prompt)
    complete_event = None
    _stream_exc = None
    try:
        src = _iter_anthropic_web(prompt, system_text, model) if uses_web else _iter_anthropic_chat(prompt, system_text, model)
        async for event in src:
            if event.get("type") == "complete":
                complete_event = event
            yield event
    except Exception as exc:
        _stream_exc = exc
        raise
    finally:
        if _stream_exc is not None:
            _lf_fail(gen, _stream_exc)
        elif complete_event is not None:
            _lf_end(gen, complete_event)
        else:
            _lf_fail(gen, RuntimeError("stream closed before complete event"))
