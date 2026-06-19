import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.models.evaluation_improvement import (
    EvaluationImprovementItem,
    EvaluationImprovementRegressionStatus,
    EvaluationImprovementStatus,
)
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.services.evaluation_regression_service import EvaluationRegressionService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def assistant_metrics(hit_at_1=0.5, hit_at_3=0.8, mrr=0.7, citation_rate=1.0, no_answer_accuracy=0.9, metadata_match_rate=0.8):
    metrics = {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "mrr": mrr,
        "citation_rate": citation_rate,
        "no_answer_accuracy": no_answer_accuracy,
        "metadata_match_rate": metadata_match_rate,
    }
    return {
        "use_metadata_filter": True,
        "use_rerank": True,
        "overall_metrics": metrics,
        "per_assistant_metrics": {"maintenance": metrics},
    }


def failed_case(case_id: str) -> dict:
    return {
        "id": case_id,
        "assistant_type": "maintenance",
        "failure_reason": "no_citation",
        "suggested_fix_type": "prompt",
    }


def make_run(
    db,
    user: User,
    metrics: dict,
    failed_cases: list[dict],
    run_label: str | None = None,
    change_type: str | None = None,
    change_summary: str | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=3,
        metrics=metrics,
        failed_cases=failed_cases,
        run_label=run_label,
        change_type=change_type,
        change_summary=change_summary,
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def make_item(db, run: EvaluationRun) -> EvaluationImprovementItem:
    item = EvaluationImprovementItem(
        evaluation_run_id=run.id,
        assistant_type="maintenance",
        fix_type="prompt",
        priority="medium",
        failed_case_count=2,
        affected_case_ids=["case_1", "case_2"],
        main_failure_reasons=["no_citation"],
        suggested_action="强化引用约束",
        status=EvaluationImprovementStatus.resolved,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_create_regression_creates_record_and_updates_item_status(db_session) -> None:
    admin = make_user(db_session, "regression-admin")
    before_run = make_run(
        db_session,
        admin,
        assistant_metrics(),
        [failed_case("case_1"), failed_case("case_2")],
        run_label="baseline_v1",
        change_type="baseline",
        change_summary="before prompt",
    )
    after_run = make_run(
        db_session,
        admin,
        assistant_metrics(hit_at_1=0.7, hit_at_3=0.9, mrr=0.82),
        [failed_case("case_2")],
        run_label="maintenance_prompt_v2",
        change_type="prompt",
        change_summary="after prompt",
    )
    item = make_item(db_session, before_run)

    regression = EvaluationRegressionService(db_session).create_regression(
        before_run.id,
        after_run.id,
        [item.id],
        admin,
        notes="prompt fix",
    )

    assert regression.regression_passed is True
    assert regression.resolved_case_ids == ["case_1"]
    assert regression.still_failed_case_ids == ["case_2"]
    assert regression.delta_metrics["mrr"] == pytest.approx(0.12)
    assert regression.before_run_label == "baseline_v1"
    assert regression.before_change_type == "baseline"
    assert regression.before_change_summary == "before prompt"
    assert regression.after_run_label == "maintenance_prompt_v2"
    assert regression.after_change_type == "prompt"
    assert regression.after_change_summary == "after prompt"
    assert regression.before_run_display["display_label"] == f"baseline_v1 · Run #{before_run.id}"
    assert regression.after_run_display["display_label"] == f"maintenance_prompt_v2 · Run #{after_run.id}"
    assert regression.before_mode_summary == "Metadata filter + Rerank"
    assert regression.after_metrics_summary["mrr"] == 0.82

    detail = EvaluationRegressionService(db_session).get_regression(regression.id)
    assert detail.before_run["display_label"] == f"baseline_v1 · Run #{before_run.id}"
    assert detail.after_run["change_type"] == "prompt"
    db_session.refresh(item)
    assert item.regression_status == EvaluationImprovementRegressionStatus.passed
    assert item.resolved_evaluation_run_id == after_run.id
    assert item.related_regression_id == regression.id


def test_delta_metrics_calculation() -> None:
    delta = EvaluationRegressionService.calculate_metric_delta(
        {"hit_at_1": 0.4, "mrr": 0.5},
        {"hit_at_1": 0.7, "mrr": 0.65},
    )

    assert delta["hit_at_1"] == pytest.approx(0.3)
    assert delta["mrr"] == pytest.approx(0.15)


def test_compare_failed_cases_identifies_resolved_and_still_failed() -> None:
    resolved, still_failed = EvaluationRegressionService.compare_failed_cases(
        before_failed_cases=[failed_case("case_1"), failed_case("case_2")],
        after_failed_cases=[failed_case("case_2")],
        affected_case_ids=["case_1", "case_2"],
    )

    assert resolved == ["case_1"]
    assert still_failed == ["case_2"]


def test_no_answer_accuracy_drop_fails_regression() -> None:
    passed = EvaluationRegressionService.determine_regression_passed(
        {"hit_at_1": 0, "hit_at_3": 0, "mrr": 0, "citation_rate": 0, "no_answer_accuracy": -0.06},
        still_failed_case_ids=[],
        resolved_case_ids=["case_1"],
    )

    assert passed is False


def test_citation_rate_drop_fails_regression() -> None:
    passed = EvaluationRegressionService.determine_regression_passed(
        {"hit_at_1": 0, "hit_at_3": 0, "mrr": 0, "citation_rate": -0.01, "no_answer_accuracy": 0},
        still_failed_case_ids=[],
        resolved_case_ids=["case_1"],
    )

    assert passed is False


def test_failed_regression_updates_item_status_failed(db_session) -> None:
    admin = make_user(db_session, "failed-regression-admin")
    before_run = make_run(db_session, admin, assistant_metrics(), [failed_case("case_1")])
    after_run = make_run(
        db_session,
        admin,
        assistant_metrics(citation_rate=0.9),
        [failed_case("case_1")],
    )
    item = make_item(db_session, before_run)

    regression = EvaluationRegressionService(db_session).create_regression(before_run.id, after_run.id, [item.id], admin)

    assert regression.regression_passed is False
    db_session.refresh(item)
    assert item.regression_status == EvaluationImprovementRegressionStatus.failed


def test_regression_summary_returns_pass_rate(db_session) -> None:
    admin = make_user(db_session, "summary-regression-admin")
    before_run = make_run(db_session, admin, assistant_metrics(), [failed_case("case_1")])
    passing_after = make_run(db_session, admin, assistant_metrics(mrr=0.85), [])
    failing_after = make_run(db_session, admin, assistant_metrics(citation_rate=0.9), [failed_case("case_1")])
    first_item = make_item(db_session, before_run)
    second_item = make_item(db_session, before_run)
    service = EvaluationRegressionService(db_session)

    service.create_regression(before_run.id, passing_after.id, [first_item.id], admin)
    service.create_regression(before_run.id, failing_after.id, [second_item.id], admin)

    summary = service.get_regression_summary()

    assert summary["total_regressions"] == 2
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["pass_rate"] == pytest.approx(0.5)
    assert summary["by_fix_type"]["prompt"] == 2


def test_non_admin_cannot_create_regression() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
