from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_real_retrieval_evaluation.py"

SPEC = importlib.util.spec_from_file_location("run_real_retrieval_evaluation", RUNNER_PATH)
assert SPEC is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_build_endpoint_single_mode() -> None:
    assert runner.build_endpoint("http://localhost:8000/", "single") == "http://localhost:8000/api/evaluation/retrieval/run"


def test_build_endpoint_compare_mode() -> None:
    assert runner.build_endpoint("http://localhost:8000", "compare") == "http://localhost:8000/api/evaluation/retrieval/compare"


def test_build_payload_omits_null_rerank_top_n() -> None:
    assert runner.build_payload(True, False, None) == {
        "use_metadata_filter": True,
        "use_rerank": False,
    }


def test_build_payload_includes_rerank_top_n() -> None:
    assert runner.build_payload(True, True, 20) == {
        "use_metadata_filter": True,
        "use_rerank": True,
        "rerank_top_n": 20,
    }


def test_requires_persistence_confirmation() -> None:
    config = runner.HarnessConfig(api_base_url="http://localhost:8000", token="secret", confirm_persist=False)

    try:
        runner.run_real_retrieval_evaluation(config, transport=lambda *_: {})
    except runner.HarnessError as exc:
        assert "--confirm-persist" in str(exc)
    else:
        raise AssertionError("expected HarnessError")


def test_requires_admin_token() -> None:
    config = runner.HarnessConfig(api_base_url="http://localhost:8000", token="", confirm_persist=True)

    try:
        runner.run_real_retrieval_evaluation(config, transport=lambda *_: {})
    except runner.HarnessError as exc:
        assert "Admin bearer token" in str(exc)
    else:
        raise AssertionError("expected HarnessError")


def test_run_real_retrieval_evaluation_uses_transport_and_redacts_token() -> None:
    calls = []

    def transport(url, token, payload, timeout):
        calls.append((url, token, payload, timeout))
        return {
            "run_id": "run-1",
            "total_cases": 5,
            "hit_at_1": 0.8,
            "hit_at_3": 1.0,
            "hit_at_5": 1.0,
            "mrr": 0.9,
            "keyword_match_rate": 0.7,
            "metadata_match_rate": 0.6,
            "no_answer_accuracy": 1.0,
            "failed_cases": [{"id": "case_1"}],
        }

    config = runner.HarnessConfig(
        api_base_url="http://localhost:8000",
        token="abcd1234SECRET",
        use_metadata_filter=True,
        use_rerank=True,
        rerank_top_n=20,
        confirm_persist=True,
    )

    result = runner.run_real_retrieval_evaluation(config, transport=transport)

    assert calls == [
        (
            "http://localhost:8000/api/evaluation/retrieval/run",
            "abcd1234SECRET",
            {"use_metadata_filter": True, "use_rerank": True, "rerank_top_n": 20},
            60.0,
        )
    ]
    assert result["request"]["token"] == "abcd...CRET"
    assert "abcd1234SECRET" not in str(result)
    assert result["summary"]["run_id"] == "run-1"
    assert result["summary"]["failed_case_count"] == 1
    assert result["persistence_confirmed"] is True


def test_compare_mode_summary() -> None:
    def transport(url, token, payload, timeout):
        return {
            "baseline": {"run_id": "a", "total_cases": 5, "hit_at_1": 0.5, "hit_at_3": 0.8, "mrr": 0.6, "failed_cases": []},
            "metadata_filter": {"run_id": "b", "total_cases": 5, "hit_at_1": 0.7, "hit_at_3": 0.9, "mrr": 0.75, "failed_cases": [{"id": "x"}]},
            "metadata_filter_rerank": {"run_id": "c", "total_cases": 5, "hit_at_1": 0.8, "hit_at_3": 1.0, "mrr": 0.85, "failed_cases": []},
            "delta": {"metadata_filter_vs_baseline": {"hit_at_1": 0.2}},
        }

    config = runner.HarnessConfig(
        api_base_url="http://localhost:8000",
        token="token",
        mode="compare",
        confirm_persist=True,
    )

    result = runner.run_real_retrieval_evaluation(config, transport=transport)

    assert result["endpoint"] == "http://localhost:8000/api/evaluation/retrieval/compare"
    assert result["summary"]["runs"]["metadata_filter"]["failed_case_count"] == 1
    assert result["summary"]["delta"] == {"metadata_filter_vs_baseline": {"hit_at_1": 0.2}}
