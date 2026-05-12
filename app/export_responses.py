"""Export saved AI responses for one company into prompt-ready text files."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import state as db
from app.models import InterviewState, Story


@dataclass(frozen=True)
class SectionExport:
    key: str
    title: str
    text_path: tuple[str, ...]
    model_path: tuple[str, ...]


SECTION_EXPORTS: tuple[SectionExport, ...] = (
    SectionExport("research", "Company Research", ("research", "raw_report"), ("research", "query_model_name")),
    SectionExport("interview_intel", "Interview Intel", ("interview_intel", "raw_report"), ("interview_intel", "query_model_name")),
    SectionExport("jd_decode", "Job Decoder", ("jd_analysis", "raw_analysis"), ("jd_analysis", "query_model_name")),
    SectionExport("resume_tailor", "Resume Tailor", ("resume_review",), ("resume_review_model_name",)),
    SectionExport("stories", "Story Bank", ("stories",), ("stories_model_name",)),
    SectionExport("pitch", "Pitch Builder", ("pitch", "value_proposition"), ("pitch", "query_model_name")),
    SectionExport("concerns", "Interviewer Concerns", ("concerns_analysis",), ("concerns_model_name",)),
    SectionExport("salary", "Salary Coaching", ("comp_data", "raw_analysis"), ("comp_data", "query_model_name")),
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


def load_states(data_file: Path) -> list[InterviewState]:
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    return [
        InterviewState.model_validate(raw_state)
        for raw_state in payload.get("states", {}).values()
    ]


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export saved AI responses for a company into company_section.txt files.",
    )
    parser.add_argument("company_name", help="Company name to search for. Pipe comments in saved applications are ignored.")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help=f"Path to saved data JSON. Defaults to {db.DATA_FILE_NAME} in the app data directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for exported text files. Defaults to the data file directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        written = export_company_responses(args.company_name, args.data_file, args.output_dir)
    except ValueError as exc:
        print(str(exc))
        return 1

    if not written:
        print(f"No saved AI responses found for company: {args.company_name}")
        return 1

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
