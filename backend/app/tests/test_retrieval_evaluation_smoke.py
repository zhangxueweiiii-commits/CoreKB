from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_retrieval_evaluation_smoke.py"

SPEC = importlib.util.spec_from_file_location("run_retrieval_evaluation_smoke", RUNNER_PATH)
assert SPEC is not None
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def _cases() -> list[dict]:
    return [
        {
            "id": "maintenance_001",
            "category": "maintenance",
            "assistant_type": "maintenance",
            "query": "A200 E12 handling",
            "expected_document": "A200 manual",
            "expected_keywords": ["E12", "sensor"],
            "expected_metadata": {"equipment_model": "A200", "fault_code": "E12"},
            "should_have_answer": True,
        },
        {
            "id": "no_answer_001",
            "category": "maintenance",
            "assistant_type": "maintenance",
            "query": "Z900 F99 handling",
            "expected_document": None,
            "expected_keywords": [],
            "expected_metadata": {},
            "should_have_answer": False,
        },
    ]


def _write_cases(tmp_path: Path, cases: list[dict] | None = None) -> Path:
    path = tmp_path / "eval_cases.json"
    path.write_text(json.dumps(cases or _cases()), encoding="utf-8")
    return path


def test_retrieval_smoke_returns_passing_metrics(tmp_path: Path) -> None:
    path = _write_cases(tmp_path)

    summary = asyncio.run(runner.run_retrieval_smoke(path))

    assert summary["smoke_passed"] is True
    assert summary["total_cases"] == 2
    assert summary["answerable_cases"] == 1
    assert summary["no_answer_cases"] == 1
    assert summary["failed_cases"] == []
    assert summary["metrics"]["hit_at_1"] == 1.0
    assert summary["metrics"]["hit_at_3"] == 1.0
    assert summary["metrics"]["mrr"] == 1.0
    assert summary["metrics"]["keyword_match_rate"] == 1.0
    assert summary["metrics"]["metadata_match_rate"] == 1.0
    assert summary["metrics"]["no_answer_accuracy"] == 1.0


def test_retrieval_smoke_uses_metadata_filter_when_enabled(tmp_path: Path) -> None:
    path = _write_cases(tmp_path)

    summary = asyncio.run(runner.run_retrieval_smoke(path, use_metadata_filter=True))

    assert summary["metadata_filter_enabled"] is True
    assert summary["metadata_filter_used_cases"] == 2


def test_retrieval_smoke_can_disable_metadata_filter(tmp_path: Path) -> None:
    path = _write_cases(tmp_path)

    summary = asyncio.run(runner.run_retrieval_smoke(path, use_metadata_filter=False))

    assert summary["metadata_filter_enabled"] is False
    assert summary["metadata_filter_used_cases"] == 0
    assert summary["smoke_passed"] is True


def test_retrieval_smoke_reports_read_only_runtime_dependencies(tmp_path: Path) -> None:
    path = _write_cases(tmp_path)

    summary = asyncio.run(runner.run_retrieval_smoke(path))

    assert summary["read_only"] is True
    assert summary["case_result_persistence"] is False
    assert summary["runtime_dependencies"] == {
        "database": False,
        "qdrant": False,
        "redis": False,
        "celery": False,
        "embedding": False,
        "rerank_provider": False,
        "llm": False,
    }


def test_retrieval_smoke_main_returns_zero_for_valid_cases(tmp_path: Path) -> None:
    path = _write_cases(tmp_path)

    exit_code = runner.main(["--cases", path.as_posix(), "--compact"])

    assert exit_code == 0


def test_retrieval_smoke_main_returns_nonzero_for_invalid_cases(tmp_path: Path) -> None:
    path = _write_cases(tmp_path, [{"id": "broken"}])

    exit_code = runner.main(["--cases", path.as_posix(), "--compact"])

    assert exit_code == 1
