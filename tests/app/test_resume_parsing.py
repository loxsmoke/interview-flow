"""Tests for DOCX parsing and heuristic resume tagging."""

import difflib
from pathlib import Path

from app.main import _extract_markdown_from_docx, _tag_resume_heuristic

DOCX_PATH = Path(__file__).parent / "Parse-Test-Resume.docx"
EXPECTED_PATH = Path(__file__).parent / "parsed-resume.txt"

SEPARATOR = "=== TAGGED OUTPUT ==="


def _load_expected():
    text = EXPECTED_PATH.read_text(encoding="utf-8")
    markdown_part, tagged_part = text.split(SEPARATOR, 1)
    markdown = markdown_part.removeprefix("=== EXTRACTED MARKDOWN ===").strip()
    tagged = tagged_part.strip()
    return markdown, tagged


def _diff(result: str, expected: str) -> str:
    diff = difflib.unified_diff(
        expected.splitlines(keepends=True),
        result.splitlines(keepends=True),
        fromfile="expected",
        tofile="result",
        lineterm="",
    )
    return "".join(diff)


def test_extracted_markdown_matches_expected():
    docx_bytes = DOCX_PATH.read_bytes()
    result = _extract_markdown_from_docx(docx_bytes).strip()
    expected_markdown, _ = _load_expected()
    assert result == expected_markdown, f"\n{_diff(result, expected_markdown)}"


def test_tagged_output_matches_expected():
    docx_bytes = DOCX_PATH.read_bytes()
    markdown = _extract_markdown_from_docx(docx_bytes)
    result = _tag_resume_heuristic(markdown).strip()
    _, expected_tagged = _load_expected()
    assert result == expected_tagged, f"\n{_diff(result, expected_tagged)}"
