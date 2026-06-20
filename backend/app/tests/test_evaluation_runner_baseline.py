from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_evaluation_baseline.py"

SPEC = importlib.util.spec_from_file_location("run_evaluation_baseline", RUNNER_PATH)
assert SPEC is not None
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def _case(case_id: str = "maintenance_001") -> dict:
    return {
        "id": case_id,
        "category": "maintenance",
        "assistant_type": "maintenance",
        "query": "A200 E12 handling",
        "expected_document": "A200 manual",
        "expected_keywords": ["E12"],
        "expected_metadata": {"equipment_model": "A200", "fault_code": "E12"},
        "should_have_answer": True,
    }


def test_load_eval_cases_reads_json_array(tmp_path: Path) -> None:
    path = tmp_path / "eval_cases.json"
    path.write_text(json.dumps([_case()]), encoding="utf-8")

    cases = runner.load_eval_cases(path)

    assert len(cases) == 1
    assert cases[0]["id"] == "maintenance_001"


def test_summarize_eval_cases_reports_fixture_coverage() -> None:
    cases = [
        _case("maintenance_001"),
        {
            **_case("no_answer_001"),
            "should_have_answer": False,
            "expected_document": None,
            "expected_keywords": [],
            "expected_metadata": {},
        },
    ]

    summary = runner.summarize_eval_cases(cases, case_file="eval_cases.json")

    assert summary["ready"] is True
    assert summary["total_cases"] == 2
    assert summary["answerable_cases"] == 1
    assert summary["no_answer_cases"] == 1
    assert summary["categories"] == {"maintenance": 2}
    assert summary["assistant_types"] == {"maintenance": 2}
    assert summary["expected_metadata_fields"] == {"equipment_model": 1, "fault_code": 1}
    assert summary["runtime_dependencies"]["database"] is False
    assert summary["runtime_dependencies"]["llm"] is False


def test_summarize_eval_cases_detects_duplicate_case_ids() -> None:
    summary = runner.summarize_eval_cases([_case("case_001"), _case("case_001")])

    assert summary["ready"] is False
    assert summary["issues"]["duplicate_case_ids"] == ["case_001"]


def test_summarize_eval_cases_detects_missing_required_fields() -> None:
    broken = _case()
    broken.pop("query")
    broken.pop("expected_metadata")

    summary = runner.summarize_eval_cases([broken])

    assert summary["ready"] is False
    assert summary["issues"]["missing_required_fields"] == [
        {"case_id": "maintenance_001", "missing_fields": ["expected_metadata", "query"]}
    ]


def test_summarize_eval_cases_tracks_unknown_metadata_fields_without_failing_readiness() -> None:
    case = _case()
    case["expected_metadata"] = {"quality_item": "appearance scratch"}

    summary = runner.summarize_eval_cases([case])

    assert summary["ready"] is True
    assert summary["unknown_metadata_fields"] == {"quality_item": 1}


def test_main_returns_nonzero_for_invalid_fixture_shape(tmp_path: Path) -> None:
    path = tmp_path / "eval_cases.json"
    path.write_text(json.dumps([{"id": "broken"}]), encoding="utf-8")

    exit_code = runner.main(["--cases", path.as_posix(), "--compact"])

    assert exit_code == 1
