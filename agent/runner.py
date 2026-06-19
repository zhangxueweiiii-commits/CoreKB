from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = REPO_ROOT / "agent" / "tasks"
RESULTS_DIR = REPO_ROOT / "agent" / "results"

REQUIRED_TASK_SECTIONS = (
    "Goal",
    "Scope",
    "Hard Constraints",
    "Acceptance Criteria",
    "Verification",
)

REQUIRED_RESULT_SECTIONS = (
    "Summary",
    "Files Changed",
    "Behavior Added",
    "Tests Run",
    "Test Result",
    "Database Impact",
    "Runtime Impact",
    "Risk Notes",
    "Rollback Notes",
    "Open Questions",
)


@dataclass(frozen=True)
class CheckResult:
    path: Path
    ok: bool
    missing_sections: tuple[str, ...]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "task"


def extract_task_id(task_path: Path) -> str:
    match = re.search(r"(task[-_ ]?\d+(?:\.\d+)?)", task_path.stem, re.IGNORECASE)
    if match:
        return slugify(match.group(1))
    return slugify(task_path.stem)


def markdown_has_heading(content: str, heading: str) -> bool:
    pattern = rf"^#+\s+{re.escape(heading)}\s*$"
    return re.search(pattern, content, re.MULTILINE | re.IGNORECASE) is not None


def check_markdown_sections(path: Path, required_sections: tuple[str, ...]) -> CheckResult:
    content = path.read_text(encoding="utf-8")
    missing = tuple(section for section in required_sections if not markdown_has_heading(content, section))
    return CheckResult(path=path, ok=not missing, missing_sections=missing)


def create_result_stub(task_path: Path, output_dir: Path = RESULTS_DIR) -> Path:
    task_id = extract_task_id(task_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_path = output_dir / f"{timestamp}_{task_id}_result.md"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(build_result_stub(task_path, task_id), encoding="utf-8")
    return result_path


def build_result_stub(task_path: Path, task_id: str) -> str:
    sections = "\n\n".join(f"## {section}\n\nTBD" for section in REQUIRED_RESULT_SECTIONS)
    relative_task = task_path.resolve().relative_to(REPO_ROOT)
    return f"# {task_id} Result\n\nTask: `{relative_task.as_posix()}`\n\n{sections}\n"


def self_check() -> list[CheckResult]:
    checks = [
        check_markdown_sections(REPO_ROOT / "agent" / "rules" / "AGENT_POLICY.md", ("Scope Control", "Production Data Safety")),
        check_markdown_sections(REPO_ROOT / "AGENTS.md", ("Project Guardrails", "Result Reporting")),
        check_markdown_sections(REPO_ROOT / "docs" / "TESTING.md", ("Canonical Backend Test Command",)),
        check_markdown_sections(REPO_ROOT / "agent" / "results" / "RESULT_CONTRACT.md", REQUIRED_RESULT_SECTIONS),
    ]
    return checks


def command_check(args: argparse.Namespace) -> int:
    checks = self_check()
    if args.task:
        checks.append(check_markdown_sections(Path(args.task), REQUIRED_TASK_SECTIONS))
    failed = [item for item in checks if not item.ok]
    for item in checks:
        relative = item.path.resolve().relative_to(REPO_ROOT)
        if item.ok:
            print(f"ok: {relative.as_posix()}")
        else:
            print(f"missing sections in {relative.as_posix()}: {', '.join(item.missing_sections)}")
    return 1 if failed else 0


def command_init_result(args: argparse.Namespace) -> int:
    task_path = Path(args.task)
    check = check_markdown_sections(task_path, REQUIRED_TASK_SECTIONS)
    if not check.ok:
        print(f"cannot create result; task is missing sections: {', '.join(check.missing_sections)}")
        return 1
    result_path = create_result_stub(task_path)
    print(result_path.resolve().relative_to(REPO_ROOT).as_posix())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CoreKB agent task runner")
    subcommands = parser.add_subparsers(dest="command", required=True)

    check = subcommands.add_parser("check", help="Validate agent workflow files and optionally a task brief")
    check.add_argument("--task", help="Path to a task markdown file to validate")
    check.set_defaults(func=command_check)

    init_result = subcommands.add_parser("init-result", help="Create a result markdown stub for a task")
    init_result.add_argument("--task", required=True, help="Path to a task markdown file")
    init_result.set_defaults(func=command_init_result)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
