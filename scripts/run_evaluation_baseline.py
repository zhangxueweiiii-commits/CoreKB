from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_CASE_FIELDS = {
    "id",
    "category",
    "query",
    "expected_document",
    "expected_keywords",
    "expected_metadata",
    "should_have_answer",
}

SUPPORTED_CATEGORIES = {"maintenance", "quality", "sop", "material"}
SUPPORTED_ASSISTANT_TYPES = {"maintenance", "quality", "sop", "material"}
SUPPORTED_METADATA_FIELDS = {
    "category",
    "doc_type",
    "equipment_model",
    "fault_code",
    "material_code",
    "product_model",
    "process_name",
    "sop_code",
    "version",
    "effective_date",
}


def load_eval_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("eval cases file must contain a JSON array")

    cases: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"eval case at index {index} must be an object")
        cases.append(item)
    return cases


def _case_label(case: dict[str, Any], index: int) -> str:
    value = case.get("id")
    if isinstance(value, str) and value:
        return value
    return f"<index:{index}>"


def summarize_eval_cases(cases: list[dict[str, Any]], case_file: str | None = None) -> dict[str, Any]:
    ids = [case.get("id") for case in cases if isinstance(case.get("id"), str)]
    duplicate_case_ids = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)

    category_counts: Counter[str] = Counter()
    assistant_type_counts: Counter[str] = Counter()
    expected_metadata_fields: Counter[str] = Counter()
    unknown_metadata_fields: Counter[str] = Counter()
    missing_required_fields: list[dict[str, Any]] = []
    invalid_categories: list[dict[str, str]] = []
    invalid_assistant_types: list[dict[str, str]] = []

    answerable_cases = 0
    no_answer_cases = 0

    for index, case in enumerate(cases):
        case_id = _case_label(case, index)
        missing = sorted(field for field in REQUIRED_CASE_FIELDS if field not in case)
        if missing:
            missing_required_fields.append({"case_id": case_id, "missing_fields": missing})

        category = case.get("category")
        if isinstance(category, str) and category:
            category_counts[category] += 1
            if category not in SUPPORTED_CATEGORIES:
                invalid_categories.append({"case_id": case_id, "category": category})

        assistant_type = case.get("assistant_type")
        if isinstance(assistant_type, str) and assistant_type:
            assistant_type_counts[assistant_type] += 1
            if assistant_type not in SUPPORTED_ASSISTANT_TYPES:
                invalid_assistant_types.append({"case_id": case_id, "assistant_type": assistant_type})

        should_have_answer = case.get("should_have_answer")
        if should_have_answer is True:
            answerable_cases += 1
        elif should_have_answer is False:
            no_answer_cases += 1

        expected_metadata = case.get("expected_metadata")
        if isinstance(expected_metadata, dict):
            for field in expected_metadata:
                expected_metadata_fields[field] += 1
                if field not in SUPPORTED_METADATA_FIELDS:
                    unknown_metadata_fields[field] += 1

    issues = {
        "duplicate_case_ids": duplicate_case_ids,
        "missing_required_fields": missing_required_fields,
        "invalid_categories": invalid_categories,
        "invalid_assistant_types": invalid_assistant_types,
    }

    ready = not any(issues.values())

    return {
        "eval_type": "fixture_baseline",
        "case_file": case_file,
        "total_cases": len(cases),
        "answerable_cases": answerable_cases,
        "no_answer_cases": no_answer_cases,
        "categories": dict(sorted(category_counts.items())),
        "assistant_types": dict(sorted(assistant_type_counts.items())),
        "expected_metadata_fields": dict(sorted(expected_metadata_fields.items())),
        "unknown_metadata_fields": dict(sorted(unknown_metadata_fields.items())),
        "issues": issues,
        "ready": ready,
        "read_only": True,
        "runtime_dependencies": {
            "database": False,
            "qdrant": False,
            "redis": False,
            "celery": False,
            "llm": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the read-only CoreKB evaluation fixture baseline")
    parser.add_argument(
        "--cases",
        default="backend/tests/evaluation/fixtures/expected/eval_cases.json",
        help="Path to eval_cases.json",
    )
    parser.add_argument("--output", help="Optional path for writing the JSON summary")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    case_path = Path(args.cases)

    try:
        cases = load_eval_cases(case_path)
        summary = summarize_eval_cases(cases, case_file=case_path.as_posix())
    except Exception as exc:
        error_summary = {
            "eval_type": "fixture_baseline",
            "case_file": case_path.as_posix(),
            "ready": False,
            "error": str(exc),
            "read_only": True,
        }
        print(json.dumps(error_summary, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    output = json.dumps(summary, ensure_ascii=False, indent=indent)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
