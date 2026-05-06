"""Persistent state manager — saves all coaching sessions to a single JSON file.

All sessions are stored together in interview-flow-data.json inside DATA_DIR.
Uses atomic write (write-to-temp then rename) to prevent corruption.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from app.models import InterviewState, CustomAction, Resume

logger = logging.getLogger(__name__)

# INTERVIEW_DATA_DIR env var lets desktop.py redirect writes to a user-writable location
# when running as a frozen PyInstaller bundle (sys._MEIPASS is read-only).
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR = Path(os.environ.get("INTERVIEW_DATA_DIR", DEFAULT_DATA_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE_NAME = "interview-flow-data.json"

# Old format: 12-char hex state IDs — used to detect legacy files during migration
_SAFE_ID = re.compile(r"^[a-f0-9]{12}$")

# Single global lock — all sessions share one file, so all writes must be serialized
_file_lock = asyncio.Lock()


def get_lock(state_id: str) -> asyncio.Lock:  # noqa: ARG001
    """Return the global write lock (all states share one file)."""
    return _file_lock


def set_data_dir(new_dir: Path) -> None:
    """Switch DATA_DIR at runtime after a successful data migration."""
    global DATA_DIR
    DATA_DIR = new_dir
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _validate_id(state_id: str) -> None:
    """Prevent path traversal via crafted state IDs."""
    if not _SAFE_ID.match(state_id):
        raise ValueError(f"Invalid state ID: {state_id!r}")


def _data_file() -> Path:
    return DATA_DIR / DATA_FILE_NAME


def _load_all() -> dict[str, InterviewState]:
    """Load all sessions from the combined data file."""
    f = _data_file()
    if not f.exists():
        return {}
    try:
        data = _json.loads(f.read_text(encoding="utf-8"))
        result: dict[str, InterviewState] = {}
        for sid, sdata in data.get("states", {}).items():
            try:
                result[sid] = InterviewState.model_validate(sdata)
            except Exception:
                logger.warning("Skipping corrupt session entry: %s", sid)
        return result
    except Exception:
        logger.warning("Could not read data file: %s", f)
        return {}


def _write_all(states: dict[str, InterviewState]) -> None:
    """Atomically write all sessions to the combined data file."""
    path = _data_file()
    payload = {
        "version": 1,
        "states": {sid: _json.loads(s.model_dump_json()) for sid, s in states.items()},
    }
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    fd_closed = False
    try:
        os.write(fd, _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        os.close(fd)
        fd_closed = True
        os.replace(tmp, path)
    except Exception:
        if not fd_closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_state(state: InterviewState) -> None:
    """Add or update a session in the combined data file."""
    state.updated_at = datetime.now().isoformat()
    states = _load_all()
    states[state.id] = state
    _write_all(states)


def load_state(state_id: str) -> InterviewState | None:
    """Load a single session by ID. Returns None if not found or ID is invalid."""
    try:
        _validate_id(state_id)
    except ValueError:
        return None
    return _load_all().get(state_id)


def list_states() -> list[dict]:
    """Return summaries of all saved sessions, newest first."""
    states = _load_all()
    summaries = []
    for s in sorted(
        states.values(),
        key=lambda x: x.updated_at or x.created_at or "",
        reverse=True,
    ):
        summaries.append({
            "id": s.id,
            "company_name": s.company_name or "(unnamed)",
            "position": s.position or "",
            "current_step": s.current_step,
            "completed_steps": s.completed_steps,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        })
    return summaries


def list_resume_library(preferred_state_id: str = "") -> list[Resume]:
    """Return a deduplicated resume library across all saved sessions."""
    states = _load_all()
    ordered_states: list[InterviewState] = []
    if preferred_state_id and preferred_state_id in states:
        ordered_states.append(states[preferred_state_id])
    ordered_states.extend(
        s for s in sorted(
            states.values(),
            key=lambda x: x.updated_at or x.created_at or "",
            reverse=True,
        )
        if s.id != preferred_state_id
    )

    resumes: list[Resume] = []
    seen: set[str] = set()
    for state in ordered_states:
        for resume in reversed(state.resumes):
            key = resume.description.strip().casefold() or resume.id
            if key in seen:
                continue
            seen.add(key)
            resumes.append(resume)
    return resumes


def delete_state(state_id: str) -> bool:
    """Remove a session from the combined file. Returns True if it existed."""
    try:
        _validate_id(state_id)
    except ValueError:
        return False
    states = _load_all()
    if state_id not in states:
        return False
    del states[state_id]
    _write_all(states)
    return True




# ── Global Custom Actions ─────────────────────────────────────────────────────

CUSTOM_ACTIONS_FILE_NAME = "custom-actions.json"


def _custom_actions_file() -> Path:
    return DATA_DIR / CUSTOM_ACTIONS_FILE_NAME


def load_custom_actions() -> list[CustomAction]:
    """Load the global custom actions list."""
    f = _custom_actions_file()
    if not f.exists():
        return []
    try:
        data = _json.loads(f.read_text(encoding="utf-8"))
        result: list[CustomAction] = []
        for item in data.get("actions", []):
            try:
                result.append(CustomAction.model_validate(item))
            except Exception:
                logger.warning("Skipping corrupt custom action entry")
        return result
    except Exception:
        logger.warning("Could not read custom actions file: %s", f)
        return []


def save_custom_actions(actions: list[CustomAction]) -> None:
    """Atomically write the global custom actions list."""
    path = _custom_actions_file()
    payload = {
        "version": 1,
        "actions": [_json.loads(a.model_dump_json()) for a in actions],
    }
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    fd_closed = False
    try:
        os.write(fd, _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        os.close(fd)
        fd_closed = True
        os.replace(tmp, path)
    except Exception:
        if not fd_closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
