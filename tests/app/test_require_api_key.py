"""Tests for require_ai_api_key() — verifies correct key is checked per provider."""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from app.main import require_ai_api_key


def _run(provider: str, env: dict):
    with patch("app.agents.streaming.get_active_provider", return_value=provider):
        with patch.dict("os.environ", env, clear=False):
            require_ai_api_key()


def _run_raises(provider: str, env: dict) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        _run(provider, env)
    assert exc_info.value.status_code == 503
    return exc_info.value


# ── Gemini ───────────────────────────────────────────────────────────────────

class TestGeminiProvider:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        exc = _run_raises("gemini", {})
        assert "GEMINI_API_KEY" in exc.detail
        assert "ANTHROPIC_API_KEY" not in exc.detail

    def test_raises_when_key_empty(self):
        exc = _run_raises("gemini", {"GEMINI_API_KEY": ""})
        assert "GEMINI_API_KEY" in exc.detail

    def test_passes_when_key_set(self):
        _run("gemini", {"GEMINI_API_KEY": "AIza-test-key"})


# ── OpenAI ───────────────────────────────────────────────────────────────────

class TestOpenAIProvider:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        exc = _run_raises("openai", {})
        assert "OPENAI_API_KEY" in exc.detail

    def test_raises_when_key_empty(self):
        exc = _run_raises("openai", {"OPENAI_API_KEY": ""})
        assert "OPENAI_API_KEY" in exc.detail

    def test_passes_when_key_set(self):
        _run("openai", {"OPENAI_API_KEY": "sk-test"})


# ── Anthropic ────────────────────────────────────────────────────────────────

class TestAnthropicProvider:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        exc = _run_raises("anthropic", {})
        assert "ANTHROPIC_API_KEY" in exc.detail

    def test_raises_when_key_empty(self):
        exc = _run_raises("anthropic", {"ANTHROPIC_API_KEY": ""})
        assert "ANTHROPIC_API_KEY" in exc.detail

    def test_raises_when_key_is_placeholder(self):
        exc = _run_raises("anthropic", {"ANTHROPIC_API_KEY": "your-key-here"})
        assert "ANTHROPIC_API_KEY" in exc.detail

    def test_passes_when_key_set(self):
        _run("anthropic", {"ANTHROPIC_API_KEY": "sk-ant-test"})


# ── Ollama ───────────────────────────────────────────────────────────────────

class TestOllamaProvider:
    def test_passes_with_no_keys_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        _run("ollama", {})
