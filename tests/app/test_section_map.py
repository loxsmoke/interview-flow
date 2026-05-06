"""Tests for section heading map markdown parsing and loading."""

import pytest
from pathlib import Path
from unittest.mock import patch

from app.main import _parse_section_map_md, _get_section_map, _TAG_SECTION_MAP


SECTION_HEADINGS_FILE = Path(__file__).parents[2] / "app" / "section-headings.md"


# ── _parse_section_map_md ────────────────────────────────────────────────────

class TestParseEmpty:
    def test_empty_string(self):
        assert _parse_section_map_md("") == {}

    def test_no_table(self):
        assert _parse_section_map_md("Just some text\nNo table here.") == {}

    def test_wrong_header(self):
        md = "| Name | Value |\n|---|---|\n| Foo | bar |"
        assert _parse_section_map_md(md) == {}


class TestParseBasic:
    TABLE = (
        "| Section type | Input text |\n"
        "|---|---|\n"
        "| summary | summary |\n"
        "| summary | professional summary |\n"
        "| skills | skills |\n"
    )

    def test_extracts_entries(self):
        result = _parse_section_map_md(self.TABLE)
        assert result["summary"] == "summary"
        assert result["professional summary"] == "summary"
        assert result["skills"] == "skills"

    def test_input_text_lowercased(self):
        md = (
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | SUMMARY |\n"
            "| summary | Professional Summary |\n"
        )
        result = _parse_section_map_md(md)
        assert "summary" in result
        assert "professional summary" in result
        assert "SUMMARY" not in result

    def test_separator_row_skipped(self):
        result = _parse_section_map_md(self.TABLE)
        # separator row cells like "---" must not appear as values
        assert "---" not in result
        assert ":---:" not in result


class TestParseTextAround:
    def test_ignores_text_before_table(self):
        md = (
            "# Section Headings\n\n"
            "Some description here.\n\n"
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | summary |\n"
        )
        result = _parse_section_map_md(md)
        assert result == {"summary": "summary"}

    def test_ignores_text_after_table(self):
        md = (
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | summary |\n"
            "\n"
            "More text after the table.\n"
        )
        result = _parse_section_map_md(md)
        assert result == {"summary": "summary"}

    def test_ignores_unrelated_table_before(self):
        md = (
            "| Col A | Col B |\n"
            "|---|---|\n"
            "| x | y |\n"
            "\n"
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | summary |\n"
        )
        result = _parse_section_map_md(md)
        assert result == {"summary": "summary"}
        assert "x" not in result


class TestParseExtraColumns:
    def test_extra_columns_ignored(self):
        md = (
            "| Section type | Input text | Notes | Priority |\n"
            "|---|---|---|---|\n"
            "| summary | summary | Used often | High |\n"
            "| skills | skills | | |\n"
        )
        result = _parse_section_map_md(md)
        assert result == {"summary": "summary", "skills": "skills"}

    def test_only_first_two_columns_used(self):
        md = (
            "| Section type | Input text | Extra |\n"
            "|---|---|---|\n"
            "| additional | education | ignore this |\n"
        )
        result = _parse_section_map_md(md)
        assert result["education"] == "additional"
        assert "ignore this" not in result


class TestParseEdgeCases:
    def test_empty_cells_skipped(self):
        md = (
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | summary |\n"
            "|  |  |\n"
            "| | |\n"
            "| additional | education |\n"
        )
        result = _parse_section_map_md(md)
        assert len(result) == 2
        assert result["summary"] == "summary"
        assert result["education"] == "additional"

    def test_later_entry_overrides_earlier(self):
        md = (
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | overview |\n"
            "| experience | overview |\n"
        )
        result = _parse_section_map_md(md)
        assert result["overview"] == "experience"

    def test_colon_separator_row_skipped(self):
        md = (
            "| Section type | Input text |\n"
            "|:---|:---|\n"
            "| summary | summary |\n"
        )
        result = _parse_section_map_md(md)
        assert result == {"summary": "summary"}


# ── _get_section_map ─────────────────────────────────────────────────────────

class TestGetSectionMap:
    def test_returns_default_when_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.main._APP_DIR", tmp_path)
        result = _get_section_map()
        assert result is _TAG_SECTION_MAP

    def test_merges_file_entries_with_defaults(self, monkeypatch, tmp_path):
        (tmp_path / "section-headings.md").write_text(
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| summary | my custom heading |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("app.main._APP_DIR", tmp_path)
        result = _get_section_map()
        assert result["my custom heading"] == "summary"
        # defaults still present
        assert result["summary"] == "summary"
        assert result["experience"] == "experience"

    def test_file_entry_overrides_default(self, monkeypatch, tmp_path):
        (tmp_path / "section-headings.md").write_text(
            "| Section type | Input text |\n"
            "|---|---|\n"
            "| skills | experience |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("app.main._APP_DIR", tmp_path)
        result = _get_section_map()
        assert result["experience"] == "skills"

    def test_falls_back_on_empty_file(self, monkeypatch, tmp_path):
        (tmp_path / "section-headings.md").write_text("", encoding="utf-8")
        monkeypatch.setattr("app.main._APP_DIR", tmp_path)
        result = _get_section_map()
        assert result is _TAG_SECTION_MAP

    def test_falls_back_on_no_matching_table(self, monkeypatch, tmp_path):
        (tmp_path / "section-headings.md").write_text(
            "| Wrong Header | Input text |\n|---|---|\n| x | y |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("app.main._APP_DIR", tmp_path)
        result = _get_section_map()
        assert result is _TAG_SECTION_MAP


# ── app/section-headings.md integrity ────────────────────────────────────────

KNOWN_SECTION_TYPES = {"summary", "experience", "skills", "additional"}


class TestSectionHeadingsFile:
    def test_file_exists(self):
        assert SECTION_HEADINGS_FILE.exists(), "app/section-headings.md not found"

    def test_file_parses_without_error(self):
        text = SECTION_HEADINGS_FILE.read_text(encoding="utf-8")
        result = _parse_section_map_md(text)
        assert len(result) > 0, "Parsed map is empty"

    def test_file_contains_all_hardcoded_entries(self):
        text = SECTION_HEADINGS_FILE.read_text(encoding="utf-8")
        parsed = _parse_section_map_md(text)
        missing = {k: v for k, v in _TAG_SECTION_MAP.items() if k not in parsed}
        assert not missing, f"Entries in _TAG_SECTION_MAP not in file (add them or remove from hardcoded map): {missing}"

    def test_file_entries_map_to_known_section_types(self):
        text = SECTION_HEADINGS_FILE.read_text(encoding="utf-8")
        parsed = _parse_section_map_md(text)
        unknown = {v for v in parsed.values() if v not in KNOWN_SECTION_TYPES}
        assert not unknown, f"Section types in file not in known types: {unknown}"
