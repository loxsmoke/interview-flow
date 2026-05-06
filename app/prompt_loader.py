"""Load prompt templates from markdown files in app/prompts/."""
from __future__ import annotations
from pathlib import Path

_DIR = Path(__file__).parent / "prompts"
_FENCE = "````"


def _extract_fence(content: str, section: str) -> str:
    """Return text between the 4-backtick fence that follows the given ## section heading."""
    heading = f"## {section}"
    section_start = content.index(heading)
    fence_start = content.index(_FENCE + "\n", section_start) + len(_FENCE) + 1
    fence_end = content.index("\n" + _FENCE, fence_start)
    return content[fence_start:fence_end]


def load_prompt(name: str) -> str:
    """Return the prompt text from the ## Prompt section of prompts/<name>.md."""
    content = (_DIR / f"{name}.md").read_text(encoding="utf-8")
    return _extract_fence(content, "Prompt")


def load_system_prompt(name: str) -> str:
    """Return the system prompt text from the ## System Prompt section of prompts/<name>.md."""
    content = (_DIR / f"{name}.md").read_text(encoding="utf-8")
    return _extract_fence(content, "System Prompt")
