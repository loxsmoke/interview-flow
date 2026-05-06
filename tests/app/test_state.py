"""Tests for persistent state manager."""

import pytest
from app.models import InterviewState, Story
import app.state as db


@pytest.fixture(autouse=True)
def use_temp_data_dir(monkeypatch, tmp_path):
    """Redirect state storage to a temp directory for each test."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    yield


class TestValidateId:
    def test_valid_hex_id(self):
        db._validate_id("abcdef012345")  # should not raise

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("abc")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("abcdef0123456")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("../../etc/pwd")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("ABCDEF012345")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("abc-def_01234")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid state ID"):
            db._validate_id("")


class TestSaveAndLoad:
    def test_save_then_load(self):
        s = InterviewState(
            job_posting="Test job",
            company_name="TestCo",
            current_step="setup",
            completed_steps=["setup"],
        )
        db.save_state(s)

        loaded = db.load_state(s.id)
        assert loaded is not None
        assert loaded.id == s.id
        assert loaded.company_name == "TestCo"
        assert loaded.completed_steps == ["setup"]

    def test_save_updates_timestamp(self):
        s = InterviewState(job_posting="Test")
        original_updated = s.updated_at
        db.save_state(s)

        loaded = db.load_state(s.id)
        assert loaded.updated_at >= original_updated

    def test_save_with_stories(self):
        s = InterviewState(job_posting="Test")
        s.stories.append(Story(title="My Story", situation="Context"))
        db.save_state(s)

        loaded = db.load_state(s.id)
        assert len(loaded.stories) == 1
        assert loaded.stories[0].title == "My Story"

    def test_load_nonexistent_returns_none(self):
        assert db.load_state("000000000000") is None

    def test_load_invalid_id_returns_none(self):
        assert db.load_state("../../etc/pwd") is None

    def test_atomic_write_creates_no_temp_files(self, tmp_path):
        s = InterviewState(job_posting="Test")
        db.save_state(s)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_overwrite_preserves_data(self):
        s = InterviewState(job_posting="Test", company_name="V1")
        db.save_state(s)

        s.company_name = "V2"
        s.completed_steps.append("research")
        db.save_state(s)

        loaded = db.load_state(s.id)
        assert loaded.company_name == "V2"
        assert "research" in loaded.completed_steps


class TestListStates:
    def test_empty(self):
        assert db.list_states() == []

    def test_lists_saved_states(self):
        s1 = InterviewState(job_posting="Job 1", company_name="Co1")
        s2 = InterviewState(job_posting="Job 2", company_name="Co2")
        db.save_state(s1)
        db.save_state(s2)

        states = db.list_states()
        assert len(states) == 2
        names = {s["company_name"] for s in states}
        assert names == {"Co1", "Co2"}

    def test_unnamed_company(self):
        s = InterviewState(job_posting="Job")
        db.save_state(s)

        states = db.list_states()
        assert states[0]["company_name"] == "(unnamed)"


class TestDeleteState:
    def test_delete_existing(self):
        s = InterviewState(job_posting="Test")
        db.save_state(s)
        assert db.load_state(s.id) is not None

        result = db.delete_state(s.id)
        assert result is True
        assert db.load_state(s.id) is None

    def test_delete_nonexistent(self):
        assert db.delete_state("000000000000") is False

    def test_delete_invalid_id(self):
        assert db.delete_state("bad-id!!") is False
