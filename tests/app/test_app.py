"""Tests for FastAPI endpoints (Claude API calls are mocked)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

import app.state as db
from app.main import app, _is_safe_url, _SAFE_ID
from app.models import InterviewState


@pytest.fixture(autouse=True)
def use_temp_data_dir(monkeypatch, tmp_path):
    """Redirect state storage to a temp directory for each test."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    yield


@pytest.fixture(autouse=True)
def mock_require_api_key():
    with patch("app.main.require_ai_api_key"):
        yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_state():
    """Create and save a sample state, return its ID."""
    s = InterviewState(
        job_posting="Senior Engineer at Acme Corp...",
        resume="10 years of experience in distributed systems...",
        company_name="Acme Corp",
        completed_steps=["setup"],
        current_step="setup",
    )
    db.save_state(s)
    return s.id


# ── Setup & State Management ────────────────────────────────────────────────

class TestSetup:
    def test_create_workflow(self, client):
        resp = client.post("/api/setup", json={
            "job_posting": "Engineer at Foo",
            "company_name": "Foo Inc",
            "resume": "My resume...",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["company_name"] == "Foo Inc"
        assert len(data["id"]) == 12

    def test_create_workflow_no_resume(self, client):
        resp = client.post("/api/setup", json={"job_posting": "Test job"})
        assert resp.status_code == 200

    def test_create_workflow_missing_job_posting(self, client):
        resp = client.post("/api/setup", json={})
        assert resp.status_code == 422


class TestStateManagement:
    def test_get_state(self, client, sample_state):
        resp = client.get(f"/api/state/{sample_state}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == "Acme Corp"
        assert data["completed_steps"] == ["setup"]

    def test_get_state_not_found(self, client):
        resp = client.get("/api/state/000000000000")
        assert resp.status_code == 404

    def test_list_states(self, client, sample_state):
        resp = client.get("/api/states")
        assert resp.status_code == 200
        states = resp.json()
        assert len(states) >= 1
        assert any(s["id"] == sample_state for s in states)

    def test_delete_state(self, client, sample_state):
        resp = client.delete(f"/api/state/{sample_state}")
        assert resp.status_code == 200

        resp = client.get(f"/api/state/{sample_state}")
        assert resp.status_code == 404


class TestIndex:
    def test_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text


# ── Stories ──────────────────────────────────────────────────────────────────

class TestStories:
    def test_get_stories_empty(self, client, sample_state):
        resp = client.get(f"/api/{sample_state}/stories")
        assert resp.status_code == 200
        assert resp.json()["stories"] == []

    def test_add_story(self, client, sample_state):
        story = {
            "title": "Led DB Migration",
            "situation": "Legacy MySQL was failing",
            "task": "Migrate to Postgres",
            "action": "Planned 3-sprint migration",
            "result": "99.9% uptime",
            "tags": ["leadership", "technical"],
        }
        resp = client.post(f"/api/{sample_state}/stories/add", json=story)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["story"]["title"] == "Led DB Migration"

    def test_delete_story(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/stories/add", json={"title": "To Delete"})
        story_id = resp.json()["story"]["id"]

        resp = client.delete(f"/api/{sample_state}/stories/{story_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @patch("app.main.mine_stories", new_callable=AsyncMock)
    def test_mine_stories(self, mock_mine, client, sample_state):
        mock_mine.return_value = {
            "stories": [
                {
                    "title": "Mined Story",
                    "situation": "Context",
                    "task": "Do the thing",
                    "action": "Did the thing",
                    "result": "Good outcome",
                    "earned_secret": "Hidden insight",
                    "tags": ["leadership"],
                    "fit_scores": {"leadership": "Strong Fit"},
                }
            ],
            "cost_usd": 0.0,
            "model_name": "test-model",
            "duration_ms": 1,
        }
        resp = client.post(f"/api/{sample_state}/stories/mine")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["stories"][0]["title"] == "Mined Story"

    def test_mine_stories_no_resume(self, client):
        resp = client.post("/api/setup", json={"job_posting": "Test job"})
        state_id = resp.json()["id"]
        resp = client.post(f"/api/{state_id}/stories/mine")
        assert resp.status_code == 400


# ── Agent Endpoints (mocked) ────────────────────────────────────────────────

class TestResearch:
    @patch("app.main.run_research", new_callable=AsyncMock)
    def test_research(self, mock_research, client, sample_state):
        mock_research.return_value = {
            "raw_report": "# Acme Corp Research\nGreat company...",
            "cost_usd": 0.05,
        }
        resp = client.post(f"/api/{sample_state}/research")
        assert resp.status_code == 200
        data = resp.json()
        assert "Acme Corp" in data["report"]
        assert data["cost_usd"] == 0.05

        state_resp = client.get(f"/api/state/{sample_state}")
        assert "research" in state_resp.json()["completed_steps"]


class TestJDDecode:
    @patch("app.main.decode_jd", new_callable=AsyncMock)
    def test_decode_jd(self, mock_decode, client, sample_state):
        mock_decode.return_value = "## JD Analysis\nRepetition: 'distributed systems' appears 5 times..."
        resp = client.post(f"/api/{sample_state}/decode-jd")
        assert resp.status_code == 200
        assert "JD Analysis" in resp.json()["analysis"]

        state_resp = client.get(f"/api/state/{sample_state}")
        assert "jd_decode" in state_resp.json()["completed_steps"]


class TestSalary:
    @patch("app.main.salary_coach", new_callable=AsyncMock)
    def test_salary_coaching(self, mock_salary, client, sample_state):
        mock_salary.return_value = "## Salary Analysis\nRange: $180K-$250K..."
        resp = client.post(f"/api/{sample_state}/salary")
        assert resp.status_code == 200
        assert "Salary Analysis" in resp.json()["analysis"]


class TestConcerns:
    @patch("app.main.anticipate_concerns", new_callable=AsyncMock)
    def test_concerns(self, mock_concerns, client, sample_state):
        mock_concerns.return_value = "## Concerns\n1. Gap in recent experience..."
        resp = client.post(f"/api/{sample_state}/concerns")
        assert resp.status_code == 200

    def test_concerns_no_resume(self, client):
        resp = client.post("/api/setup", json={"job_posting": "Test"})
        state_id = resp.json()["id"]
        resp = client.post(f"/api/{state_id}/concerns")
        assert resp.status_code == 400


class TestPitch:
    @patch("app.main.build_pitches", new_callable=AsyncMock)
    def test_pitch(self, mock_pitch, client, sample_state):
        mock_pitch.return_value = "## Pitches\n10s: I'm a senior engineer..."
        resp = client.post(f"/api/{sample_state}/pitch")
        assert resp.status_code == 200

    def test_pitch_no_resume(self, client):
        resp = client.post("/api/setup", json={"job_posting": "Test"})
        state_id = resp.json()["id"]
        resp = client.post(f"/api/{state_id}/pitch")
        assert resp.status_code == 400


# ── Debrief ──────────────────────────────────────────────────────────────────

class TestDebrief:
    def test_save_debrief(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/debrief", json={"notes": "Interview went well"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        state = client.get(f"/api/state/{sample_state}").json()
        assert "Interview went well" in state["debrief_notes"]
        assert "debrief" in state["completed_steps"]

    def test_debrief_empty_notes(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/debrief", json={"notes": ""})
        assert resp.status_code == 200


# ── Resume Upload ────────────────────────────────────────────────────────────

class TestResumeUpload:
    def test_upload_txt_resume(self, client):
        content = b"John Doe\n10 years of experience in distributed systems."
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "John Doe" in data["text"]
        assert data["filename"] == "resume.txt"
        assert data["chars"] > 0

    def test_upload_md_resume(self, client):
        content = b"# Jane Smith\n\n## Experience\n- 5 years Python"
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.md", content, "text/markdown")},
        )
        assert resp.status_code == 200
        assert "Jane Smith" in resp.json()["text"]

    def test_upload_unsupported_extension(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.jpg", b"fake image", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_upload_empty_file(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Could not extract any text" in resp.json()["detail"]

    def test_upload_whitespace_only(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", b"   \n\n  \t  ", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Could not extract any text" in resp.json()["detail"]

    def test_upload_too_large(self, client):
        # 11 MB of data should exceed the 10 MB limit
        big_content = b"x" * (11 * 1024 * 1024)
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", big_content, "text/plain")},
        )
        assert resp.status_code == 400
        assert "File too large" in resp.json()["detail"]

    def test_upload_no_file(self, client):
        resp = client.post("/api/upload-resume")
        assert resp.status_code == 422

    @patch("app.main._extract_text_from_pdf")
    def test_upload_pdf_calls_extractor(self, mock_pdf_extract, client):
        mock_pdf_extract.return_value = "Extracted PDF resume content"
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Extracted PDF resume content"
        mock_pdf_extract.assert_called_once()

    @patch("app.main._extract_markdown_from_docx")
    @patch("app.main._extract_text_from_docx")
    def test_upload_docx_calls_extractor(self, mock_docx_extract, mock_markdown_extract, client):
        mock_markdown_extract.return_value = "Extracted DOCX resume content"
        mock_docx_extract.return_value = "Raw DOCX resume content"
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.docx", b"PK\x03\x04 fake docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Extracted DOCX resume content"
        assert resp.json()["raw"] == "Raw DOCX resume content"
        mock_markdown_extract.assert_called_once()
        mock_docx_extract.assert_called_once()

    @patch("app.main._extract_text")
    def test_upload_extraction_error(self, mock_extract, client):
        mock_extract.side_effect = RuntimeError("corrupt file")
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", b"some content", "text/plain")},
        )
        assert resp.status_code == 500
        assert "Could not extract text" in resp.json()["detail"]


# ── Progress ─────────────────────────────────────────────────────────────────

class TestProgress:
    def test_add_progress(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/progress", json={
            "event_type": "mock",
            "notes": "Practiced behavioral",
            "scores": {"substance": 4.0, "structure": 3.5},
        })
        assert resp.status_code == 200
        assert resp.json()["total_entries"] == 1


# ── Security Tests ──────────────────────────────────────────────────────────

class TestSSRFPrevention:
    """Verify _is_safe_url blocks private/internal IPs."""

    def test_blocks_localhost(self):
        assert _is_safe_url("http://localhost/admin") is False
        assert _is_safe_url("http://127.0.0.1/admin") is False

    def test_blocks_private_ranges(self):
        assert _is_safe_url("http://10.0.0.1/internal") is False
        assert _is_safe_url("http://172.16.0.1/internal") is False
        assert _is_safe_url("http://192.168.1.1/internal") is False

    def test_blocks_link_local(self):
        assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_empty_host(self):
        assert _is_safe_url("http://") is False
        assert _is_safe_url("") is False

    def test_blocks_malformed_url(self):
        assert _is_safe_url("not-a-url") is False

    @patch("app.main.socket.gethostbyname", return_value="93.184.216.34")
    def test_allows_public_ip(self, mock_dns):
        assert _is_safe_url("https://example.com/job-posting") is True

    def test_url_fetch_blocked_for_private_ip(self, client, sample_state):
        """Verify that resolve_job_posting rejects private URLs at the API level."""
        resp = client.post("/api/setup", json={
            "job_posting": "http://169.254.169.254/latest/meta-data/",
            "company_name": "Evil Corp",
        })
        assert resp.status_code == 200
        # The URL should be returned as-is (not fetched)
        state_id = resp.json()["id"]
        state = client.get(f"/api/state/{state_id}").json()
        assert state["job_posting"] == "http://169.254.169.254/latest/meta-data/"


class TestMagicByteValidation:
    """Verify file uploads are validated by magic bytes, not just extension."""

    def test_rejects_pdf_with_wrong_magic_bytes(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("exploit.pdf", b"NOT-A-PDF malicious content", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "valid PDF" in resp.json()["detail"]

    def test_rejects_docx_with_wrong_magic_bytes(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("exploit.docx", b"NOT-A-DOCX malicious content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 400
        assert "valid DOCX" in resp.json()["detail"]

    @patch("app.main._extract_text_from_pdf")
    def test_accepts_pdf_with_correct_magic_bytes(self, mock_extract, client):
        mock_extract.return_value = "Valid PDF content"
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.pdf", b"%PDF-1.7 content here", "application/pdf")},
        )
        assert resp.status_code == 200

    @patch("app.main._extract_markdown_from_docx")
    @patch("app.main._extract_text_from_docx")
    def test_accepts_docx_with_correct_magic_bytes(self, mock_extract, mock_markdown_extract, client):
        mock_markdown_extract.return_value = "Valid DOCX content"
        mock_extract.return_value = "Raw DOCX content"
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.docx", b"PK\x03\x04 content here", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200

    def test_txt_files_skip_magic_byte_check(self, client):
        resp = client.post(
            "/api/upload-resume",
            files={"file": ("resume.txt", b"Any content is fine for txt", "text/plain")},
        )
        assert resp.status_code == 200


class TestInputLengthLimits:
    """Verify max_length constraints on text inputs."""

    def test_rejects_oversized_job_posting(self, client):
        resp = client.post("/api/setup", json={
            "job_posting": "x" * 100_001,
            "company_name": "Test",
        })
        assert resp.status_code == 422

    def test_rejects_oversized_resume_in_setup(self, client):
        resp = client.post("/api/setup", json={
            "job_posting": "Valid job posting",
            "resume": "x" * 100_001,
        })
        assert resp.status_code == 422

    def test_rejects_oversized_company_name(self, client):
        resp = client.post("/api/setup", json={
            "job_posting": "Valid job posting",
            "company_name": "x" * 501,
        })
        assert resp.status_code == 422

    def test_rejects_oversized_resume_update(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/resume-update", json={
            "resume": "x" * 100_001,
        })
        assert resp.status_code == 422

    def test_rejects_oversized_debrief_notes(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/debrief", json={
            "notes": "x" * 50_001,
        })
        assert resp.status_code == 422

    def test_rejects_oversized_chat_message(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/resume-chat/respond", json={
            "message": "x" * 50_001,
            "session_id": "fake_session",
        })
        assert resp.status_code == 422

    def test_accepts_valid_length_inputs(self, client):
        resp = client.post("/api/setup", json={
            "job_posting": "Valid job posting under limit",
            "resume": "Valid resume under limit",
            "company_name": "Acme Corp",
        })
        assert resp.status_code == 200


class TestStoryIdValidation:
    """Verify story_id path param is format-validated."""

    def test_rejects_invalid_story_id(self, client, sample_state):
        resp = client.delete(f"/api/{sample_state}/stories/XXXXXX!!@@##")
        assert resp.status_code == 400
        assert "Invalid story ID" in resp.json()["detail"]

    def test_rejects_too_short_story_id(self, client, sample_state):
        resp = client.delete(f"/api/{sample_state}/stories/abc")
        assert resp.status_code == 400

    def test_rejects_special_chars_story_id(self, client, sample_state):
        resp = client.delete(f"/api/{sample_state}/stories/abcdef-12345")
        assert resp.status_code == 400

    def test_accepts_valid_story_id(self, client, sample_state):
        # Add a story first, then delete by its valid ID
        resp = client.post(f"/api/{sample_state}/stories/add", json={"title": "Deletable"})
        story_id = resp.json()["story"]["id"]
        assert len(story_id) == 12

        resp = client.delete(f"/api/{sample_state}/stories/{story_id}")
        assert resp.status_code == 200


class TestServerMintedStoryIds:
    """Verify server always mints fresh story IDs regardless of client input."""

    def test_ignores_client_supplied_id(self, client, sample_state):
        resp = client.post(f"/api/{sample_state}/stories/add", json={
            "id": "aaaaaaaaaaaa",
            "title": "Client Controlled ID",
        })
        assert resp.status_code == 200
        # Server should mint a new ID, not use the client's
        assert resp.json()["story"]["id"] != "aaaaaaaaaaaa"

    def test_two_stories_get_different_ids(self, client, sample_state):
        r1 = client.post(f"/api/{sample_state}/stories/add", json={"title": "Story 1"})
        r2 = client.post(f"/api/{sample_state}/stories/add", json={"title": "Story 2"})
        assert r1.json()["story"]["id"] != r2.json()["story"]["id"]
