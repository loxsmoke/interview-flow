"""Tests for queue worker section-to-state mappings."""

import asyncio
import json
import re
import shutil
from pathlib import Path

import pytest

import app.state as db
from app.models import CustomAction, InterviewState
from app.state import save_custom_actions

import app.main as app_mod


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isolated_data_dir(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)
    data_dir = Path(".test-data") / safe_name
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)

    original_data_dir = db.DATA_DIR
    db.set_data_dir(data_dir)
    yield
    db.set_data_dir(original_data_dir)
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def sample_state():
    state = InterviewState(
        job_posting="Senior Engineer role with Python and distributed systems.",
        resume="Built distributed systems and led migrations.",
        company_name="Acme",
        completed_steps=["setup"],
    )
    db.save_state(state)
    return state


async def fake_text_stream(text: str):
    yield {"type": "send", "channel": "user", "text": "prompt"}
    yield {
        "type": "complete",
        "text": text,
        "cost_usd": 1.25,
        "model_name": "test-model",
        "duration_ms": 321,
    }


async def consume_queue_stream(state_id: str, section_key: str) -> list[dict]:
    events = []
    async for chunk in app_mod._queued_section_stream(state_id, section_key):
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest.mark.parametrize(
    ("section_key", "stream_attr", "text", "state_assertion"),
    [
        (
            "research",
            "stream_research",
            "Research report",
            lambda state, text: state.research.raw_report == text
            and state.research.query_cost_usd == 1.25
            and state.current_step == "research",
        ),
        (
            "interview_intel",
            "stream_interview_intel",
            "Interview intel report",
            lambda state, text: state.interview_intel.raw_report == text
            and state.interview_intel.query_model_name == "test-model"
            and state.current_step == "interview_intel",
        ),
        (
            "jd_decode",
            "stream_decode_jd",
            "JD analysis",
            lambda state, text: state.jd_analysis.raw_analysis == text
            and state.jd_analysis.query_duration_ms == 321,
        ),
        (
            "resume_tailor",
            "stream_resume_review",
            "Resume review",
            lambda state, text: state.resume_review == text
            and state.resume_review_cost_usd == 1.25,
        ),
        (
            "pitch",
            "stream_build_pitches",
            "Pitch variants",
            lambda state, text: state.pitch.value_proposition == text
            and state.pitch.query_model_name == "test-model",
        ),
        (
            "concerns",
            "stream_anticipate_concerns",
            "Concern analysis",
            lambda state, text: state.concerns_analysis == text
            and state.concerns_duration_ms == 321,
        ),
        (
            "salary",
            "stream_salary_coach",
            "Salary analysis",
            lambda state, text: state.comp_data.raw_analysis == text
            and state.comp_data.query_cost_usd == 1.25,
        ),
    ],
)
def test_queued_text_sections_save_to_matching_state_fields(
    monkeypatch,
    sample_state,
    section_key,
    stream_attr,
    text,
    state_assertion,
):
    monkeypatch.setattr(app_mod, "require_ai_api_key", lambda: None)
    monkeypatch.setattr(app_mod, stream_attr, lambda *args, **kwargs: fake_text_stream(text))

    events = run(consume_queue_stream(sample_state.id, section_key))
    saved = db.load_state(sample_state.id)

    assert events[-1]["type"] == "complete"
    assert events[-1]["result"] == text
    assert section_key in saved.completed_steps
    assert state_assertion(saved, text)


def test_queued_story_mapping_appends_stories_and_metadata(monkeypatch, sample_state):
    monkeypatch.setattr(app_mod, "require_ai_api_key", lambda: None)
    story_payload = [
        {
            "title": "Migration Story",
            "situation": "Legacy DB",
            "task": "Move safely",
            "action": "Dual writes",
            "result": "No downtime",
            "earned_secret": "Trust first",
            "tags": ["technical"],
            "fit_scores": {"technical": "Strong Fit"},
        }
    ]
    monkeypatch.setattr(
        app_mod,
        "stream_mine_stories",
        lambda *args, **kwargs: fake_text_stream(json.dumps(story_payload)),
    )

    events = run(consume_queue_stream(sample_state.id, "stories"))
    saved = db.load_state(sample_state.id)

    assert events[-1]["type"] == "complete"
    assert events[-1]["stories"][0]["title"] == "Migration Story"
    assert saved.stories[0].title == "Migration Story"
    assert saved.stories_cost_usd == 1.25
    assert saved.stories_model_name == "test-model"
    assert "stories" in saved.completed_steps


def test_queued_custom_action_saves_under_action_name(monkeypatch, sample_state):
    monkeypatch.setattr(app_mod, "require_ai_api_key", lambda: None)
    action = CustomAction(
        id="aaaaaaaaaaaa",
        name="Cover Letter",
        prompt_template="Write using {{resume}}",
    )
    save_custom_actions([action])

    import app.agents.streaming as streaming_mod

    monkeypatch.setattr(
        streaming_mod,
        "iter_text_query",
        lambda *args, **kwargs: fake_text_stream("Custom output"),
    )

    events = run(consume_queue_stream(sample_state.id, "custom:aaaaaaaaaaaa"))
    saved = db.load_state(sample_state.id)

    assert events[-1]["type"] == "complete"
    assert events[-1]["result"] == "Custom output"
    assert saved.custom_action_results["Cover Letter"].result == "Custom output"
    assert saved.custom_action_results["Cover Letter"].model_name == "test-model"
    assert "custom_aaaaaaaaaaaa" in saved.completed_steps
