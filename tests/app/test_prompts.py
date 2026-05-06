"""Temporary tests: verify each extracted prompt file matches the original hardcoded constant."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.prompt_loader import load_prompt
from app.agents.research import RESEARCH_PROMPT
from app.agents.story_miner import (
    MINING_PROMPT,
    RESUME_REVIEW_PROMPT,
    JD_DECODE_PROMPT,
    SALARY_PROMPT,
    CONCERNS_PROMPT,
    INTERVIEW_INTEL_PROMPT,
    TECHNICAL_SECTION_TEMPLATE,
    PITCH_PROMPT,
)
from app.agents.mock_interview import MOCK_SYSTEM_PROMPT
from app.agents.resume_chat import RESUME_CHAT_SYSTEM


def test_research():
    assert load_prompt("research") == RESEARCH_PROMPT

def test_story_mining():
    assert load_prompt("story_mining") == MINING_PROMPT

def test_resume_review():
    assert load_prompt("resume_review") == RESUME_REVIEW_PROMPT

def test_jd_decode():
    assert load_prompt("jd_decode") == JD_DECODE_PROMPT

def test_salary_coach():
    assert load_prompt("salary_coach") == SALARY_PROMPT

def test_concerns():
    assert load_prompt("concerns") == CONCERNS_PROMPT

def test_interview_intel():
    assert load_prompt("interview_intel") == INTERVIEW_INTEL_PROMPT

def test_interview_intel_technical():
    assert load_prompt("interview_intel_technical") == TECHNICAL_SECTION_TEMPLATE

def test_pitch():
    assert load_prompt("pitch") == PITCH_PROMPT

def test_mock_interview():
    assert load_prompt("mock_interview") == MOCK_SYSTEM_PROMPT

def test_resume_chat():
    assert load_prompt("resume_chat") == RESUME_CHAT_SYSTEM
