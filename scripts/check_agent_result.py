from __future__ import annotations

import argparse
import glob
import re
from pathlib import Path


REQUIRED_RESULT_SECTIONS = (
    "Summary",
    "Files Changed",
    "Behavior Added",
    "Tests Run",
    "Test Result",
    "Runtime Impact",
    "Database Impact",
    "Risk Notes",
    "Rollback Notes",
    "Open Questions",
)


def expand_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(pattern))
    return paths


def markdown_has_heading(content: str, heading: str) -> bool:
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    return re.search(pattern, content, re.MULTILINE | re.IGNORECASE) is not None


def check_result_file(path: Path) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, [f"file does not exist: {path.as_posix()}"]
    if not path.name.endswith("_result.md"):
        return False, [f"result file must end with _result.md: {path.as_posix()}"]

    content = path.read_text(encoding="utf-8")
    errors = [
        f"missing required section: {section}"
        for section in REQUIRED_RESULT_SECTIONS
        if not markdown_has_heading(content, section)
    ]
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CoreKB agent result markdown files")
    parser.add_argument("paths", nargs="+", help="Result file paths or glob patterns")
    args = parser.parse_args()

    paths = expand_paths(args.paths)
    if not paths:
        print("no result files matched")
        return 1

    failed = False
    for path in paths:
        ok, errors = check_result_file(path)
        if ok:
            print(f"ok: {path.as_posix()}")
            continue
        failed = True
        print(f"failed: {path.as_posix()}")
        for error in errors:
            print(f"  - {error}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
