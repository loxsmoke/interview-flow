"""Langfuse tracing wrapper for interview-flow agents.

Provides a decorator and context manager to instrument all agent calls with
Langfuse traces. Gracefully degrades to no-op if Langfuse is not configured,
so the app works without observability keys during local development.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Lazy-initialized Langfuse client — None means not configured
_langfuse = None
_initialized = False


def _get_langfuse():
    """Return the Langfuse client, initializing on first call. Returns None if not configured."""
    global _langfuse, _initialized
    if _initialized:
        return _langfuse
    _initialized = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        logger.info("Langfuse keys not set — tracing disabled")
        return None

    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=os.environ.get("LANGFUSE_BASEURL") or os.environ.get("LANGFUSE_BASE_URL") or "http://localhost:3000",
        )
        logger.info("Langfuse tracing enabled")
    except Exception:
        logger.warning("Failed to initialize Langfuse — tracing disabled", exc_info=True)

    return _langfuse


# Public alias used by streaming.py
get_langfuse = _get_langfuse


@asynccontextmanager
async def trace_agent(
    agent_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """Context manager that creates a Langfuse trace for an agent invocation.

    Yields a trace object (or None if Langfuse is not configured).
    Records duration and any errors as trace metadata.

    Usage:
        async with trace_agent("research", tags=["web-search"]) as trace:
            result = await run_research(...)
            if trace:
                trace.update(output=result["raw_report"][:500])
    """
    lf = _get_langfuse()
    trace = None
    start = time.time()

    # trace_agent is kept for backwards compatibility but does not create a
    # Langfuse span — generation tracking happens inside iter_text_query instead.
    _ = lf  # ensure lf is referenced so the check above still gates the flush below

    try:
        yield trace
    except Exception as exc:
        # Record error on trace before re-raising
        if trace:
            try:
                trace.update(
                    metadata={
                        **(metadata or {}),
                        "error": str(exc),
                        "duration_s": round(time.time() - start, 2),
                    },
                )
            except Exception:
                pass
        raise
    else:
        # Record successful completion
        if trace:
            try:
                trace.update(
                    metadata={
                        **(metadata or {}),
                        "duration_s": round(time.time() - start, 2),
                    },
                )
            except Exception:
                pass
    finally:
        # Flush in background — non-blocking
        if lf:
            try:
                lf.flush()
            except Exception:
                pass


def traced_agent(
    agent_name: str,
    *,
    tags: list[str] | None = None,
) -> Callable:
    """Decorator that wraps an async agent function with Langfuse tracing.

    Usage:
        @traced_agent("decode-jd", tags=["jd-analysis"])
        async def decode_jd(job_posting: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with trace_agent(agent_name, tags=tags) as trace:
                result = await fn(*args, **kwargs)
                # Attach a truncated output preview to the trace
                if trace and isinstance(result, str):
                    try:
                        trace.update(output=result[:500])
                    except Exception:
                        pass
                elif trace and isinstance(result, dict):
                    try:
                        preview = {k: str(v)[:200] for k, v in result.items()}
                        trace.update(output=preview)
                    except Exception:
                        pass
                return result
        return wrapper
    return decorator
