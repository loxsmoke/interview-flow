"""Tests for exporting company AI responses."""

import json

import pytest

from app.export_responses import base_company_name, export_company_responses, matching_states
from app.models import InterviewState, Story


def write_data(path, states):
    payload = {
        "version": 1,
        "states": {state.id: json.loads(state.model_dump_json()) for state in states},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_base_company_name_strips_pipe_comment_and_spaces():
    assert base_company_name("  Visa | cloud migration role ") == "Visa"
    assert base_company_name("Stripe") == "Stripe"


def test_matching_states_uses_base_company_name_case_insensitively():
    visa = InterviewState(company_name="Visa | first")
    visa_other = InterviewState(company_name=" visa ")
    other = InterviewState(company_name="Visage")

    assert matching_states([visa, visa_other, other], "VISA") == [visa, visa_other]


def test_export_company_responses_writes_multiple_applications_for_same_section(tmp_path):
    first = InterviewState(company_name="Acme | backend", position="Staff Engineer")
    first.research.raw_report = "First research"
    first.research.query_model_name = "model-a"

    second = InterviewState(company_name="Acme | platform")
    second.research.raw_report = "Second research"
    second.research.query_model_name = "model-b"

    data_file = tmp_path / "interview-flow-data.json"
    out_dir = tmp_path / "exports"
    write_data(data_file, [first, second])

    written = export_company_responses(" Acme ", data_file=data_file, output_dir=out_dir)

    assert written == [out_dir / "Acme_research.txt"]
    text = written[0].read_text(encoding="utf-8")
    assert text.startswith("Model: model-a\n")
    assert "Application: Acme | backend" in text
    assert "Position: Staff Engineer" in text
    assert "Output:\nFirst research" in text
    assert "---" in text
    assert "Model: model-b\n" in text
    assert "Output:\nSecond research" in text


def test_export_company_responses_writes_only_sections_with_output(tmp_path):
    state = InterviewState(company_name="Acme")
    state.resume_review = "Resume review output"
    state.resume_review_model_name = "resume-model"

    data_file = tmp_path / "interview-flow-data.json"
    out_dir = tmp_path / "exports"
    write_data(data_file, [state])

    written = export_company_responses("Acme", data_file=data_file, output_dir=out_dir)

    assert written == [out_dir / "Acme_resume_tailor.txt"]
    assert not (out_dir / "Acme_research.txt").exists()


def test_export_company_responses_formats_stories_as_prompt_text(tmp_path):
    state = InterviewState(company_name="Acme")
    state.stories = [Story(title="Migration", situation="Legacy service", action="Moved it")]
    state.stories_model_name = "story-model"

    data_file = tmp_path / "interview-flow-data.json"
    out_dir = tmp_path / "exports"
    write_data(data_file, [state])

    written = export_company_responses("Acme", data_file=data_file, output_dir=out_dir)

    assert written == [out_dir / "Acme_stories.txt"]
    text = written[0].read_text(encoding="utf-8")
    assert text.startswith("Model: story-model\n")
    assert "### Migration" in text
    assert "Situation: Legacy service" in text


def test_export_company_responses_errors_when_company_not_found(tmp_path):
    data_file = tmp_path / "interview-flow-data.json"
    write_data(data_file, [InterviewState(company_name="Other")])

    with pytest.raises(ValueError, match="No applications found"):
        export_company_responses("Acme", data_file=data_file, output_dir=tmp_path)
