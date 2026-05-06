"""Pydantic models for the Interview Flow system."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)
from datetime import datetime
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Resume Library ───────────────────────────────────────────────────────────

class Resume(BaseModel):
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""
    text: str = ""


# ── Custom Actions ────────────────────────────────────────────────────────────

class CustomAction(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = "Custom Action"
    description: str = ""
    prompt_template: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CustomActionResult(BaseModel):
    result: str = ""
    cost_usd: float = 0.0
    model_name: str = ""
    duration_ms: int = 0
    ran_at: str = ""


# ── Story Bank ───────────────────────────────────────────────────────────────

class Story(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    tags: list[str] = []
    earned_secret: str = ""  # the spiky, proprietary insight
    fit_scores: dict[str, str] = {}  # question_type -> Strong Fit|Workable|Stretch|Gap
    times_used: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Mock Interview ───────────────────────────────────────────────────────────

class InterviewQuestion(BaseModel):
    question: str
    answer: str = ""
    scores: dict[str, int] = {}  # dimension -> 1-5
    feedback: str = ""
    interviewer_thoughts: str = ""


class MockSession(BaseModel):
    id: str = Field(default_factory=new_id)
    format: str = "behavioral"  # behavioral|system_design|case_study|panel|bar_raiser
    questions: list[InterviewQuestion] = []
    overall_scores: dict[str, float] = {}
    bottleneck: str = ""
    root_cause: str = ""
    summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Research Outputs ─────────────────────────────────────────────────────────

class CompanyResearch(BaseModel):
    company_name: str = ""
    summary: str = ""
    culture: str = ""
    reputation: str = ""
    tech_stack: list[str] = []
    products: list[str] = []
    challenges: list[str] = []
    green_flags: list[str] = []
    red_flags: list[str] = []
    fit_score: int = 0  # 0-100
    raw_report: str = ""
    query_cost_usd: float = 0.0
    query_model_name: str = ""
    query_duration_ms: int = 0
    query_ran_at: str = ""
    researched_at: str = ""


class JDAnalysis(BaseModel):
    raw_jd: str = ""
    requirements: list[str] = []
    nice_to_haves: list[str] = []
    hidden_signals: list[str] = []
    cultural_cues: list[str] = []
    missing_signals: list[str] = []
    confidence_tags: dict[str, str] = {}  # requirement -> HIGH|MEDIUM|LOW
    raw_analysis: str = ""
    query_cost_usd: float = 0.0
    query_model_name: str = ""
    query_duration_ms: int = 0
    query_ran_at: str = ""


# ── Interview Intel ──────────────────────────────────────────────────────────

class InterviewIntel(BaseModel):
    raw_report: str = ""
    query_cost_usd: float = 0.0
    query_model_name: str = ""
    query_duration_ms: int = 0
    query_ran_at: str = ""


# ── Salary & Negotiation ────────────────────────────────────────────────────

class CompData(BaseModel):
    range_low: int = 0
    range_high: int = 0
    equity_notes: str = ""
    negotiation_scripts: list[str] = []
    fallback_language: list[str] = []
    raw_analysis: str = ""
    query_cost_usd: float = 0.0
    query_model_name: str = ""
    query_duration_ms: int = 0
    query_ran_at: str = ""


# ── Interview Pitch ──────────────────────────────────────────────────────────

class Pitch(BaseModel):
    elevator_10s: str = ""
    networking_30s: str = ""
    recruiter_60s: str = ""
    interview_90s: str = ""
    value_proposition: str = ""
    query_cost_usd: float = 0.0
    query_model_name: str = ""
    query_duration_ms: int = 0
    query_ran_at: str = ""
    talking_points: list[str] = []
    thirty_sixty_ninety: str = ""


# ── Progress Tracking ────────────────────────────────────────────────────────

class ProgressEntry(BaseModel):
    date: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str = ""  # mock|real_interview|debrief|rejection
    notes: str = ""
    scores: dict[str, float] = {}
    self_assessment: dict[str, float] = {}


# ── Master State ─────────────────────────────────────────────────────────────

class InterviewState(BaseModel):
    """Full persistent state for one job opportunity."""
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Inputs
    job_posting: str = ""
    resume: str = ""
    resume_raw: str = ""  # TEMPORARY: diagnostic format from DOCX extraction
    resumes: list[Resume] = []
    custom_action_results: dict[str, CustomActionResult] = Field(default_factory=dict)
    company_name: str = ""
    position: str = ""

    # Workflow outputs
    research: CompanyResearch = Field(default_factory=CompanyResearch)
    interview_intel: InterviewIntel = Field(default_factory=InterviewIntel)
    jd_analysis: JDAnalysis = Field(default_factory=JDAnalysis)
    stories: list[Story] = []
    stories_cost_usd: float = 0.0
    stories_model_name: str = ""
    stories_duration_ms: int = 0
    stories_ran_at: str = ""
    mock_sessions: list[MockSession] = []
    comp_data: CompData = Field(default_factory=CompData)
    pitch: Pitch = Field(default_factory=Pitch)
    progress: list[ProgressEntry] = []

    # Resume tailoring
    resume_review: str = ""  # AI analysis of resume vs JD fit
    resume_review_cost_usd: float = 0.0
    resume_review_model_name: str = ""
    resume_review_duration_ms: int = 0
    resume_review_ran_at: str = ""
    tailored_resume: str = ""  # User-edited tailored resume
    resume_tagged: str = ""   # Heuristic-tagged version of resume for docx export

    # Concerns & follow-ups
    concerns_analysis: str = ""  # Full concerns anticipation report
    concerns_cost_usd: float = 0.0
    concerns_model_name: str = ""
    concerns_duration_ms: int = 0
    concerns_ran_at: str = ""
    interviewer_concerns: list[dict[str, str]] = []  # [{concern, counter_evidence}]
    thank_you_drafts: list[str] = []
    debrief_notes: list[str] = []

    # Workflow tracking
    completed_steps: list[str] = []
    current_step: str = "setup"


# ── API Request / Response ───────────────────────────────────────────────────

class SetupRequest(BaseModel):
    job_posting: str = Field(max_length=100_000)
    resume: str = Field(default="", max_length=100_000)
    resume_raw: str = Field(default="", max_length=500_000)
    company_name: str = Field(default="", max_length=500)
    position: str = Field(default="", max_length=500)


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class MockInterviewRequest(BaseModel):
    format: str = "behavioral"  # behavioral|system_design|case_study|panel
    message: str = ""  # for continuing a session
    session_id: str = ""  # empty = new session


class StoryRequest(BaseModel):
    action: str = "mine"  # mine | add | edit | delete
    story: Optional[Story] = None
    story_id: str = ""
