"""Shared fixtures and mocks for all tests."""

import sys
import types
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock
import pytest


_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


@pytest.fixture()
def tmp_path(tmp_path_factory):
    """Override tmp_path to use tests/.tmp, avoiding Windows AppData permission errors."""
    return tmp_path_factory.mktemp("t")


@pytest.fixture(scope="session")
def tmp_path_factory(request):
    """Override tmp_path_factory to use tests/.tmp directly."""
    import tempfile, uuid

    class _Factory:
        def mktemp(self, basename, numbered=True):
            _TMP_ROOT.mkdir(parents=True, exist_ok=True)
            suffix = f"-{uuid.uuid4().hex[:8]}" if numbered else ""
            p = _TMP_ROOT / f"{basename}{suffix}"
            p.mkdir(parents=True, exist_ok=True)
            return p

    return _Factory()

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ── Mock claude_agent_sdk before any project module imports it ───────────────
# This must happen before importing app, agents, etc.

mock_sdk = types.ModuleType("claude_agent_sdk")
mock_sdk.query = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_sdk.AssistantMessage = type("AssistantMessage", (), {"content": []})
mock_sdk.TextBlock = type("TextBlock", (), {"text": ""})
mock_sdk.ResultMessage = type("ResultMessage", (), {"total_cost_usd": 0.0})
mock_sdk.ToolUseBlock = MagicMock()
mock_sdk.ThinkingBlock = MagicMock()
sys.modules["claude_agent_sdk"] = mock_sdk

# ── Mock langfuse before any project module imports tracing ──────────────────
# Prevents tests from requiring Langfuse credentials or network access.

mock_langfuse_mod = types.ModuleType("langfuse")
mock_langfuse_mod.Langfuse = MagicMock()
sys.modules["langfuse"] = mock_langfuse_mod
