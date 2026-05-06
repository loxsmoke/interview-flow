"""Tests for _build_export_filename."""

import pytest
from app.main import _build_export_filename

DATE = "20260506"


class TestFullName:
    def test_all_parts_present(self):
        assert _build_export_filename("John Smith", "Google", DATE) == "John_Smith_Resume_20260506_Google.docx"

    def test_empty_name_omitted(self):
        assert _build_export_filename("", "Google", DATE) == "Resume_20260506_Google.docx"

    def test_empty_company_omitted(self):
        assert _build_export_filename("John Smith", "", DATE) == "John_Smith_Resume_20260506.docx"

    def test_both_empty(self):
        assert _build_export_filename("", "", DATE) == "Resume_20260506.docx"

    def test_whitespace_only_name_omitted(self):
        assert _build_export_filename("   ", "Acme", DATE) == "Resume_20260506_Acme.docx"

    def test_whitespace_only_company_omitted(self):
        assert _build_export_filename("Jane Doe", "   ", DATE) == "Jane_Doe_Resume_20260506.docx"


class TestNamePipe:
    def test_pipe_suffix_dropped(self):
        assert _build_export_filename("John Smith | Senior Engineer", "Acme", DATE) == "John_Smith_Resume_20260506_Acme.docx"

    def test_pipe_with_no_name_before(self):
        result = _build_export_filename("| something", "Acme", DATE)
        assert result == "Resume_20260506_Acme.docx"

    def test_pipe_in_company_not_dropped(self):
        # company field doesn't have the pipe rule; but | is stripped as unsafe
        result = _build_export_filename("Jane Doe", "Big | Corp", DATE)
        assert "Big" in result
        assert "|" not in result


class TestSpaces:
    def test_spaces_replaced_with_underscore(self):
        assert _build_export_filename("Mary Jane Watson", "New Corp", DATE) == "Mary_Jane_Watson_Resume_20260506_New_Corp.docx"

    def test_multiple_spaces_collapsed(self):
        result = _build_export_filename("John  Smith", "Acme", DATE)
        assert "John_Smith" in result
        assert "__" not in result


class TestSpecialChars:
    def test_unsafe_chars_removed_from_name(self):
        result = _build_export_filename("Jöhn <Smith>", "Acme", DATE)
        assert "<" not in result
        assert ">" not in result

    def test_unsafe_chars_removed_from_company(self):
        stem = _build_export_filename("John Smith", "Acme/Corp: Ltd.", DATE).removesuffix(".docx")
        assert "/" not in stem
        assert ":" not in stem
        assert "." not in stem

    def test_hyphen_kept(self):
        result = _build_export_filename("Mary-Jane Smith", "Acme-Corp", DATE)
        assert "Mary-Jane_Smith" in result
        assert "Acme-Corp" in result

    def test_no_double_underscores(self):
        result = _build_export_filename("John Smith", "Google", DATE)
        assert "__" not in result


class TestDateDefault:
    def test_date_uses_today_when_none(self):
        from datetime import datetime
        result = _build_export_filename("John Smith", "Acme")
        today = datetime.now().strftime("%Y%m%d")
        assert today in result

    def test_date_appears_after_resume_keyword(self):
        result = _build_export_filename("John Smith", "Acme", DATE)
        parts = result.replace(".docx", "").split("_")
        resume_idx = parts.index("Resume")
        assert parts[resume_idx + 1] == DATE
