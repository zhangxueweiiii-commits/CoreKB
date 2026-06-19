import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import compare_evaluation_runs
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.services.evaluation_run_compare_service import EvaluationRunCompareService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def config(
    signature: str = "sig-a",
    use_metadata_filter: bool = True,
    use_rerank: bool = True,
    rerank_top_n: int | None = 20,
    assistant_types: list[str] | None = None,
) -> dict:
    return {
        "eval_type": "assistant",
        "assistant_types": assistant_types or ["maintenance"],
        "use_metadata_filter": use_metadata_filter,
        "use_rerank": use_rerank,
        "rerank_top_n": rerank_top_n,
        "evaluation_case_set_signature": signature,
        "evaluation_case_ids": ["case_1", "case_2", "case_3", "case_4"],
    }


def metrics(hit_at_1: float = 0.5, hit_at_3: float = 0.8, mrr: float = 0.7) -> dict:
    values = {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": 0.9,
        "mrr": mrr,
        "citation_rate": 1.0,
        "no_answer_accuracy": 0.9,
        "metadata_match_rate": 0.8,
    }
    return {
        "use_metadata_filter": True,
        "use_rerank": True,
        "rerank_top_n": 20,
        "overall_metrics": values,
        "per_assistant_metrics": {"maintenance": values},
    }


def failed_case(case_id: str, reason: str = "no_citation") -> dict:
    return {
        "id": case_id,
        "assistant_type": "maintenance",
        "query": f"query {case_id}",
        "failure_reason": reason,
        "suggested_fix_type": "prompt",
        "actual_top_documents": [f"{case_id}.txt"],
        "used_metadata_filter": {"category": "maintenance"},
    }


def make_run(
    db,
    user: User,
    failed_cases: list[dict],
    run_metrics: dict | None = None,
    snapshot: dict | None = None,
    run_label: str | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=4,
        metrics=run_metrics or metrics(),
        failed_cases=failed_cases,
        config_snapshot=snapshot or config(),
        run_label=run_label,
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_same_case_set_signature_is_comparable(db_session) -> None:
    admin = make_user(db_session, "compare-admin")
    before = make_run(db_session, admin, [failed_case("case_1")])
    after = make_run(db_session, admin, [])

    result = EvaluationRunCompareService(db_session).compare_evaluation_runs(before.id, after.id)

    assert result["comparable"] is True
    assert result["comparability_warnings"] == []


def test_different_case_set_signature_warns(db_session) -> None:
    admin = make_user(db_session, "compare-signature-admin")
    before = make_run(db_session, admin, [], snapshot=config(signature="sig-a"))
    after = make_run(db_session, admin, [], snapshot=config(signature="sig-b"))

    result = EvaluationRunCompareService(db_session).compare_evaluation_runs(before.id, after.id)

    assert result["comparable"] is False
    assert "evaluation_case_set_signature 不一致" in result["comparability_warnings"]


def test_metrics_diff_calculation() -> None:
    diff = EvaluationRunCompareService.calculate_metrics_diff(
        {"hit_at_1": 0.4, "hit_at_3": 0.8, "mrr": 0.6},
        {"hit_at_1": 0.7, "hit_at_3": 0.7, "mrr": 0.75},
    )

    assert diff["hit_at_1"] == pytest.approx(0.3)
    assert diff["hit_at_3"] == pytest.approx(-0.1)
    assert diff["mrr"] == pytest.approx(0.15)


def test_failed_case_diff_groups_resolved_introduced_and_still_failed(db_session) -> None:
    admin = make_user(db_session, "compare-diff-admin")
    before = make_run(db_session, admin, [failed_case("case_1"), failed_case("case_2")])
    after = make_run(db_session, admin, [failed_case("case_2"), failed_case("case_3")])

    diff = EvaluationRunCompareService(db_session).compare_failed_cases(before, after)

    assert [item["case_id"] for item in diff["resolved_cases"]] == ["case_1"]
    assert [item["case_id"] for item in diff["introduced_failures"]] == ["case_3"]
    assert [item["case_id"] for item in diff["still_failed_cases"]] == ["case_2"]
    assert diff["unchanged_passed_count"] == 1
    assert diff["before_failed_count"] == 2
    assert diff["after_failed_count"] == 2


def test_metadata_filter_and_rerank_config_changes_warn(db_session) -> None:
    admin = make_user(db_session, "compare-config-admin")
    before = make_run(db_session, admin, [], snapshot=config(use_metadata_filter=False, use_rerank=False, rerank_top_n=10))
    after = make_run(db_session, admin, [], snapshot=config(use_metadata_filter=True, use_rerank=True, rerank_top_n=20))

    result = EvaluationRunCompareService(db_session).compare_evaluation_runs(before.id, after.id)

    assert result["comparable"] is True
    assert "use_metadata_filter 不一致" in result["comparability_warnings"]
    assert "use_rerank 不一致" in result["comparability_warnings"]
    assert "rerank_top_n 不一致" in result["comparability_warnings"]
    assert any("检索配置变化" in warning for warning in result["comparability_warnings"])


def test_compare_api_returns_run_display(db_session) -> None:
    admin = make_user(db_session, "compare-route-admin")
    before = make_run(db_session, admin, [failed_case("case_1")], run_label="baseline_v1")
    after = make_run(db_session, admin, [], run_metrics=metrics(hit_at_1=0.8, mrr=0.85), run_label="prompt_v2")

    result = compare_evaluation_runs(before.id, after.id, admin, db_session)

    assert result["before_run"]["display_label"] == f"baseline_v1 · Run #{before.id}"
    assert result["after_run"]["display_label"] == f"prompt_v2 · Run #{after.id}"
    assert result["metric_deltas"]["hit_at_1"] == pytest.approx(0.3)


def test_non_admin_cannot_access_compare_api() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
