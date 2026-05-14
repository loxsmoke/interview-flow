"""Export saved AI responses for one company into prompt-ready text files."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app import state as db
from app.models import InterviewState, Story
from app.agents.research import build_research_prompt, RESEARCH_SYSTEM_PROMPT
from app.agents.story_miner import (
    build_interview_intel_prompt, INTERVIEW_INTEL_SYSTEM_PROMPT,
    build_decode_jd_prompt, JD_DECODE_SYSTEM_PROMPT,
    build_resume_review_prompt, RESUME_REVIEW_SYSTEM_PROMPT,
    MINING_PROMPT, MINING_SYSTEM_PROMPT,
    build_pitch_prompt, PITCH_SYSTEM_PROMPT,
    build_concerns_prompt, CONCERNS_SYSTEM_PROMPT,
    build_salary_prompt, SALARY_SYSTEM_PROMPT,
)


@dataclass(frozen=True)
class SectionExport:
    key: str
    title: str
    text_path: tuple[str, ...]
    model_path: tuple[str, ...]
    eval_prompt: str = ""


_EVAL_FORMAT = (
    "For each output use exactly this structure:\n"
    "**Model**: <model name>\n"
    "**Score**: <X>/10\n"
    "**Summary**: 1-2 sentences describing what the output covers and its overall quality.\n"
    "**Key aspects**:\n"
    "- <aspect or strength>\n"
    "- <aspect or strength>\n"
    "- <gap or weakness if any>\n"
    "(3-5 bullet points)\n\n"
    "After all outputs, add a **Ranking** section that lists every evaluated model from best to worst, "
    "showing each model's name and score (e.g. '1. ModelName — 8/10')."
)

SECTION_EXPORTS: tuple[SectionExport, ...] = (
    SectionExport(
        "research", "Company Research",
        ("research", "raw_report"), ("research", "query_model_name"),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated company research reports for a job application.\n"
            "Score each output 1-10 on: factual accuracy and source quality, completeness of coverage, "
            "and actionability for the candidate's decision-making.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "interview_intel", "Interview Intel",
        ("interview_intel", "raw_report"), ("interview_intel", "query_model_name"),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated interview intelligence reports for a job application.\n"
            "Score each output 1-10 on: relevance of insights to the specific role, depth of interview process "
            "detail, and usefulness of the preparation advice.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "jd_decode", "Job Decoder",
        ("jd_analysis", "raw_analysis"), ("jd_analysis", "query_model_name"),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated job description analyses for a job application.\n"
            "Score each output 1-10 on: accuracy in identifying hard requirements vs. nice-to-haves, "
            "quality of hidden signal detection, and usefulness of cultural and strategic cues surfaced.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "resume_tailor", "Resume Tailor",
        ("resume_review",), ("resume_review_model_name",),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated resume tailoring reviews for a job application.\n"
            "Score each output 1-10 on: specificity of recommendations, alignment with the role's requirements, "
            "and clarity of the suggested edits.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "stories", "Story Bank",
        ("stories",), ("stories_model_name",),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated STAR story banks for a job application.\n"
            "Score each output 1-10 on: story relevance to the target role, strength and specificity of "
            "results, and overall variety across the story set.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "pitch", "Pitch Builder",
        ("pitch", "value_proposition"), ("pitch", "query_model_name"),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated candidate pitch / value proposition statements "
            "for a job application.\n"
            "Score each output 1-10 on: persuasiveness, authenticity and fit with the role, "
            "and clarity of the candidate's unique value.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "concerns", "Interviewer Concerns",
        ("concerns_analysis",), ("concerns_model_name",),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated interviewer concerns analyses for a job application.\n"
            "Score each output 1-10 on: accuracy in predicting likely objections, quality of the suggested "
            "responses, and completeness of coverage across risk areas.\n\n"
            + _EVAL_FORMAT
        ),
    ),
    SectionExport(
        "salary", "Salary Coaching",
        ("comp_data", "raw_analysis"), ("comp_data", "query_model_name"),
        eval_prompt=(
            "You are a judge evaluating multiple AI-generated salary coaching reports for a job application.\n"
            "Score each output 1-10 on: accuracy and recency of market compensation data, "
            "quality of negotiation strategy, and actionability of the advice.\n\n"
            + _EVAL_FORMAT
        ),
    ),
)


def base_company_name(company_name: str) -> str:
    """Return the searchable company name before a pipe comment."""
    return company_name.split("|", 1)[0].strip()


def _filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    return cleaned or "company"


def _value_at(obj: Any, path: tuple[str, ...]) -> Any:
    current = obj
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _stories_as_text(stories: list[Story]) -> str:
    parts = []
    for story in stories:
        parts.append(
            f"### {story.title}\n"
            f"- Situation: {story.situation}\n"
            f"- Task: {story.task}\n"
            f"- Action: {story.action}\n"
            f"- Result: {story.result}\n"
            f"- Earned Secret: {story.earned_secret}\n"
            f"- Tags: {', '.join(story.tags)}"
        )
    return "\n\n".join(parts)


def _section_text(state: InterviewState, section: SectionExport) -> str:
    value = _value_at(state, section.text_path)
    if section.key == "stories":
        return _stories_as_text(value or []) if value else ""
    if isinstance(value, str):
        return value.strip()
    if value:
        return json.dumps(value, ensure_ascii=False, indent=2).strip()
    return ""


def _section_model(state: InterviewState, section: SectionExport) -> str:
    value = _value_at(state, section.model_path)
    return value.strip() if isinstance(value, str) and value.strip() else "Unknown model"


def _format_response_block(state: InterviewState, section: SectionExport, text: str) -> str:
    position = state.position.strip() if state.position else ""
    application = state.company_name.strip() or "(unnamed application)"
    lines = [
        f"Model: {_section_model(state, section)}",
        f"Application: {application}",
    ]
    if position:
        lines.append(f"Position: {position}")
    lines.extend([
        f"Section: {section.title}",
        "Output:",
        text.strip(),
    ])
    return "\n".join(lines).strip()


def _build_section_prompt(section: SectionExport, state: InterviewState) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) exactly as the app generates them."""
    jd = state.job_posting
    resume = state.resume
    company = base_company_name(state.company_name)
    position = state.position.strip()
    builders: dict[str, tuple[str, str]] = {
        "research":       (RESEARCH_SYSTEM_PROMPT,       build_research_prompt(jd, resume)),
        "interview_intel":(INTERVIEW_INTEL_SYSTEM_PROMPT, build_interview_intel_prompt(company, jd, position)),
        "jd_decode":      (JD_DECODE_SYSTEM_PROMPT,      build_decode_jd_prompt(jd)),
        "resume_tailor":  (RESUME_REVIEW_SYSTEM_PROMPT,  build_resume_review_prompt(jd, resume)),
        "stories":        (MINING_SYSTEM_PROMPT,          MINING_PROMPT.format(resume=resume, job_posting=jd, existing_stories="None")),
        "pitch":          (PITCH_SYSTEM_PROMPT,           build_pitch_prompt(jd, resume)),
        "concerns":       (CONCERNS_SYSTEM_PROMPT,        build_concerns_prompt(jd, resume)),
        "salary":         (SALARY_SYSTEM_PROMPT,          build_salary_prompt(jd, resume)),
    }
    return builders[section.key]


def _format_eval_file(
    section: SectionExport,
    system_prompt: str,
    user_prompt: str,
    outputs: list[tuple[str, str]],
) -> str:
    parts = [
        f'<eval_prompt section="{section.title}">\n{section.eval_prompt}\n</eval_prompt>',
        f"<system_prompt>\n{system_prompt}\n</system_prompt>",
        f"<user_prompt>\n{user_prompt}\n</user_prompt>",
    ]
    for model, text in outputs:
        parts.append(f'<output model="{model}">\n{text}\n</output>')
    return "\n\n".join(parts) + "\n"


def load_states(data_file: Path) -> list[InterviewState]:
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    return [
        InterviewState.model_validate(raw_state)
        for raw_state in payload.get("states", {}).values()
    ]


def list_companies(data_file: Path) -> None:
    states = load_states(data_file)
    if not states:
        print("No applications found.")
        return

    companies: dict[str, tuple[str, list[str]]] = {}  # name -> (latest_created_at, models)
    for state in states:
        name = base_company_name(state.company_name)
        model = state.research.query_model_name.strip() if state.research.query_model_name else ""
        if name not in companies:
            companies[name] = (state.created_at, [])
        latest, models = companies[name]
        if state.created_at > latest:
            latest = state.created_at
        if model and model not in models:
            models.append(model)
        companies[name] = (latest, models)

    sorted_companies = sorted(companies.items(), key=lambda x: x[1][0], reverse=True)

    col_company = max(len("Company"), max(len(name) for name in companies))
    print(f"{'Company':<{col_company}}  Research Models")
    print("-" * (col_company + 42))
    for name, (_, models) in sorted_companies:
        model_str = ", ".join(sorted(models)) if models else "-"
        print(f"{name:<{col_company}}  {model_str}")


def matching_states(states: list[InterviewState], company_name: str) -> list[InterviewState]:
    target = base_company_name(company_name).casefold()
    return [
        state
        for state in states
        if base_company_name(state.company_name).casefold() == target
    ]


def export_company_responses(company_name: str, data_file: Path | None = None, output_dir: Path | None = None) -> list[Path]:
    data_file = data_file or (db.DATA_DIR / db.DATA_FILE_NAME)
    output_dir = output_dir or data_file.parent

    states = matching_states(load_states(data_file), company_name)
    if not states:
        raise ValueError(f"No applications found for company: {company_name}")

    output_dir.mkdir(parents=True, exist_ok=True)
    company_part = _filename_part(base_company_name(company_name))
    written: list[Path] = []

    for section in SECTION_EXPORTS:
        blocks = [
            _format_response_block(state, section, text)
            for state in states
            if (text := _section_text(state, section))
        ]
        if not blocks:
            continue

        path = output_dir / f"{company_part}_{section.key}.txt"
        path.write_text("\n\n---\n\n".join(blocks) + "\n", encoding="utf-8")
        written.append(path)

    return written


def export_company_eval(company_name: str, data_file: Path | None = None, output_dir: Path | None = None) -> list[Path]:
    data_file = data_file or (db.DATA_DIR / db.DATA_FILE_NAME)
    output_dir = output_dir or data_file.parent

    states = matching_states(load_states(data_file), company_name)
    if not states:
        raise ValueError(f"No applications found for company: {company_name}")

    company = base_company_name(company_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    company_part = _filename_part(company)
    # Use the first state with a job posting to build prompts; fall back to first state.
    prompt_state = next((s for s in states if s.job_posting.strip()), states[0])
    written: list[Path] = []

    for section in SECTION_EXPORTS:
        seen_models: set[str] = set()
        outputs: list[tuple[str, str]] = []
        for state in states:
            text = _section_text(state, section)
            if not text:
                continue
            model = _section_model(state, section)
            if model in seen_models:
                continue
            seen_models.add(model)
            outputs.append((model, text))

        if len(outputs) < 2:
            continue

        system_prompt, user_prompt = _build_section_prompt(section, prompt_state)
        path = output_dir / f"{company_part}_{section.key}_eval.txt"
        path.write_text(_format_eval_file(section, system_prompt, user_prompt, outputs), encoding="utf-8")
        written.append(path)

    return written


def build_parser() -> argparse.ArgumentParser:
    default_data_file = db.DATA_DIR / db.DATA_FILE_NAME
    parser = argparse.ArgumentParser(
        description="Export saved AI responses for a company into company_section.txt files.",
    )
    parser.add_argument("company_name", nargs="?", help="Company name to search for. Pipe comments in saved applications are ignored.")
    parser.add_argument(
        "-d", "--data-file",
        type=Path,
        default=default_data_file,
        help=f"Path to saved data JSON. Defaults to {default_data_file}.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="Directory for exported text files. Defaults to the data file directory.",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all saved applications with their Research model and exit.",
    )
    parser.add_argument(
        "-e", "--eval",
        action="store_true",
        help="Export eval files (one per section with 2+ LLM outputs) instead of plain exports.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.data_file.exists():
        print(f"Data file not found: {args.data_file}")
        return 1
    if args.list:
        list_companies(args.data_file)
        return 0
    if not args.company_name:
        build_parser().error("company_name is required unless --list is specified")
    try:
        if args.eval:
            written = export_company_eval(args.company_name, args.data_file, args.output_dir)
        else:
            written = export_company_responses(args.company_name, args.data_file, args.output_dir)
    except ValueError as exc:
        print(str(exc))
        return 1

    if not written:
        label = "eval" if args.eval else "AI response"
        print(f"No {label} files written for company: {args.company_name}")
        return 1

    for path in written:
        print(f"{path}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
