"""Tests for Pydantic models."""

import pytest
from app.models import (
    Story, MockSession, InterviewQuestion, InterviewState,
    CompanyResearch, JDAnalysis, CompData, Pitch, ProgressEntry,
    SetupRequest, MockInterviewRequest, StoryRequest, ChatMessage,
    new_id,
)


class TestNewId:
    def test_returns_12_char_hex(self):
        id_ = new_id()
        assert len(id_) == 12
        assert all(c in "0123456789abcdef" for c in id_)

    def test_unique(self):
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100


class TestStory:
    def test_defaults(self):
        s = Story(title="Test Story")
        assert s.title == "Test Story"
        assert s.situation == ""
        assert s.tags == []
        assert s.fit_scores == {}
        assert s.times_used == 0
        assert len(s.id) == 12
        assert s.created_at  # non-empty

    def test_full_story(self):
        s = Story(
            title="Led Migration",
            situation="Legacy DB was failing",
            task="Migrate to Postgres",
            action="Planned and executed in 3 sprints",
            result="99.9% uptime, 40% cost reduction",
            earned_secret="The real bottleneck was political, not technical",
            tags=["leadership", "technical"],
            fit_scores={"leadership": "Strong Fit", "technical_challenge": "Strong Fit"},
        )
        assert s.tags == ["leadership", "technical"]
        assert s.fit_scores["leadership"] == "Strong Fit"

    def test_roundtrip_json(self):
        s = Story(title="Roundtrip Test")
        json_str = s.model_dump_json()
        s2 = Story.model_validate_json(json_str)
        assert s2.title == s.title
        assert s2.id == s.id


class TestInterviewQuestion:
    def test_defaults(self):
        q = InterviewQuestion(question="Tell me about yourself")
        assert q.answer == ""
        assert q.scores == {}
        assert q.interviewer_thoughts == ""


class TestMockSession:
    def test_defaults(self):
        ms = MockSession()
        assert ms.format == "behavioral"
        assert ms.questions == []
        assert ms.bottleneck == ""

    def test_with_questions(self):
        ms = MockSession(
            format="system_design",
            questions=[InterviewQuestion(question="Design Twitter")],
        )
        assert len(ms.questions) == 1
        assert ms.questions[0].question == "Design Twitter"


class TestCompanyResearch:
    def test_defaults(self):
        cr = CompanyResearch()
        assert cr.company_name == ""
        assert cr.tech_stack == []
        assert cr.fit_score == 0


class TestJDAnalysis:
    def test_defaults(self):
        jd = JDAnalysis()
        assert jd.requirements == []
        assert jd.confidence_tags == {}


class TestCompData:
    def test_defaults(self):
        cd = CompData()
        assert cd.range_low == 0
        assert cd.negotiation_scripts == []


class TestPitch:
    def test_defaults(self):
        p = Pitch()
        assert p.elevator_10s == ""
        assert p.talking_points == []


class TestProgressEntry:
    def test_defaults(self):
        pe = ProgressEntry()
        assert pe.event_type == ""
        assert pe.date  # non-empty


class TestInterviewState:
    def test_defaults(self):
        s = InterviewState()
        assert len(s.id) == 12
        assert s.job_posting == ""
        assert s.current_step == "setup"
        assert s.completed_steps == []
        assert isinstance(s.research, CompanyResearch)
        assert s.stories == []

    def test_full_state_roundtrip(self):
        s = InterviewState(
            job_posting="Senior Engineer at Acme",
            resume="10 years experience...",
            company_name="Acme Corp",
            completed_steps=["setup", "research"],
            current_step="research",
        )
        s.stories.append(Story(title="Led Migration"))
        s.debrief_notes.append("Went well")

        json_str = s.model_dump_json()
        s2 = InterviewState.model_validate_json(json_str)
        assert s2.company_name == "Acme Corp"
        assert len(s2.stories) == 1
        assert s2.stories[0].title == "Led Migration"
        assert s2.debrief_notes == ["Went well"]
        assert s2.completed_steps == ["setup", "research"]

    def test_nested_defaults_are_independent(self):
        """Ensure default_factory prevents shared mutable defaults."""
        s1 = InterviewState()
        s2 = InterviewState()
        s1.completed_steps.append("setup")
        assert s2.completed_steps == []  # must not be shared


class TestRequestModels:
    def test_setup_request(self):
        r = SetupRequest(job_posting="Engineer at Foo")
        assert r.resume == ""
        assert r.company_name == ""

    def test_setup_request_requires_job_posting(self):
        with pytest.raises(Exception):
            SetupRequest()  # job_posting is required

    def test_mock_interview_request(self):
        r = MockInterviewRequest()
        assert r.format == "behavioral"
        assert r.message == ""
        assert r.session_id == ""

    def test_chat_message(self):
        m = ChatMessage(role="user", content="Hello")
        assert m.role == "user"

    def test_story_request(self):
        r = StoryRequest()
        assert r.action == "mine"
        assert r.story is None
