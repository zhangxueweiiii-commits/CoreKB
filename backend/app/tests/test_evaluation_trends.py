from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import assistant_metric_trends
from app.models.evaluation_regression import EvaluationRegression
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.services.evaluation_trend_service import EvaluationTrendService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def metrics(
    hit_at_1=0.8,
    hit_at_3=0.9,
    hit_at_5=1.0,
    mrr=0.84,
    keyword_match_rate=0.8,
    metadata_match_rate=0.9,
    no_answer_accuracy=0.9,
    citation_rate=1.0,
    quality_gate_passed=True,
) -> dict:
    return {
        "assistant_type": "maintenance",
        "total_cases": 5,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "mrr": mrr,
        "keyword_match_rate": keyword_match_rate,
        "metadata_match_rate": metadata_match_rate,
        "no_answer_accuracy": no_answer_accuracy,
        "citation_rate": citation_rate,
        "quality_gate_passed": quality_gate_passed,
    }


def make_run(
    db,
    user: User,
    created_at: datetime,
    assistant_metrics: dict,
    use_metadata_filter=True,
    use_rerank=True,
    mode="metadata_filter_rerank",
    run_label: str | None = None,
    change_type: str | None = None,
    change_summary: str | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=5,
        metrics={
            "use_metadata_filter": use_metadata_filter,
            "use_rerank": use_rerank,
            "mode": mode,
            "overall_metrics": assistant_metrics,
            "per_assistant_metrics": {
                "maintenance": assistant_metrics,
                "quality": {**assistant_metrics, "assistant_type": "quality", "hit_at_1": 0.5},
            },
        },
        failed_cases=[],
        run_label=run_label,
        change_type=change_type,
        change_summary=change_summary,
        config_snapshot={"use_metadata_filter": use_metadata_filter, "use_rerank": use_rerank},
        created_by=user.id,
        created_at=created_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_evaluation_trend_service_reads_assistant_trends(db_session) -> None:
    admin = make_user(db_session, "trend-admin")
    now = datetime.now(UTC)
    make_run(db_session, admin, now - timedelta(days=1), metrics(hit_at_1=0.7))
    latest = make_run(
        db_session,
        admin,
        now,
        metrics(hit_at_1=0.8),
        run_label="maintenance_prompt_v2",
        change_type="prompt",
        change_summary="tighten prompt",
    )

    result = EvaluationTrendService(db_session).get_assistant_metric_trends(assistant_type="maintenance")

    assert result["assistant_type"] == "maintenance"
    assert result["items"][0]["evaluation_run_id"] == latest.id
    assert result["items"][0]["hit_at_1"] == 0.8
    assert result["items"][0]["run_label"] == "maintenance_prompt_v2"
    assert result["items"][0]["change_type"] == "prompt"
    assert result["items"][0]["change_summary"] == "tighten prompt"
    assert result["items"][0]["config_snapshot"]["use_rerank"] is True


def test_overall_trends_are_sorted_by_created_at_desc(db_session) -> None:
    admin = make_user(db_session, "overall-trend-admin")
    now = datetime.now(UTC)
    older = make_run(db_session, admin, now - timedelta(days=2), metrics(hit_at_1=0.6))
    newer = make_run(db_session, admin, now - timedelta(days=1), metrics(hit_at_1=0.7))

    result = EvaluationTrendService(db_session).get_overall_metric_trends()

    assert [item["evaluation_run_id"] for item in result["items"][:2]] == [newer.id, older.id]


def test_regression_trends_calculate_pass_rate(db_session) -> None:
    admin = make_user(db_session, "regression-trend-admin")
    run_id = uuid.uuid4()
    db_session.add_all(
        [
            EvaluationRegression(
                before_evaluation_run_id=run_id,
                after_evaluation_run_id=run_id,
                improvement_item_ids=[],
                assistant_type="maintenance",
                fix_type="prompt",
                before_metrics={},
                after_metrics={},
                delta_metrics={},
                affected_case_ids=[],
                resolved_case_ids=["case_1"],
                still_failed_case_ids=[],
                regression_passed=True,
                created_by=admin.id,
            ),
            EvaluationRegression(
                before_evaluation_run_id=run_id,
                after_evaluation_run_id=run_id,
                improvement_item_ids=[],
                assistant_type="maintenance",
                fix_type="rerank",
                before_metrics={},
                after_metrics={},
                delta_metrics={},
                affected_case_ids=[],
                resolved_case_ids=[],
                still_failed_case_ids=["case_2"],
                regression_passed=False,
                created_by=admin.id,
            ),
        ]
    )
    db_session.commit()

    result = EvaluationTrendService(db_session).get_regression_trends()

    assert result["total_regressions"] == 2
    assert result["passed_count"] == 1
    assert result["failed_count"] == 1
    assert result["pass_rate"] == pytest.approx(0.5)


def test_delta_from_previous_calculation() -> None:
    delta = EvaluationTrendService.calculate_trend_delta(
        {"hit_at_1": 0.8, "mrr": 0.84},
        {"hit_at_1": 0.75, "mrr": 0.81},
    )

    assert delta["hit_at_1"] == pytest.approx(0.05)
    assert delta["mrr"] == pytest.approx(0.03)


def test_hit_at_1_drop_creates_regression_warning() -> None:
    warnings = EvaluationTrendService.detect_metric_regression(
        {"hit_at_1": 0.7, "quality_gate_passed": True},
        {"hit_at_1": 0.8, "quality_gate_passed": True},
    )

    assert warnings[0]["metric"] == "hit_at_1"
    assert warnings[0]["level"] == "warning"


def test_citation_rate_drop_creates_regression_warning() -> None:
    warnings = EvaluationTrendService.detect_metric_regression(
        {"citation_rate": 0.99, "quality_gate_passed": True},
        {"citation_rate": 1.0, "quality_gate_passed": True},
    )

    assert any(item["metric"] == "citation_rate" for item in warnings)


def test_quality_gate_pass_to_fail_creates_regression_warning() -> None:
    warnings = EvaluationTrendService.detect_metric_regression(
        {"quality_gate_passed": False},
        {"quality_gate_passed": True},
    )

    assert any(item["metric"] == "quality_gate_passed" for item in warnings)


def test_trends_api_supports_assistant_type_filter(db_session) -> None:
    admin = make_user(db_session, "trend-filter-admin")
    make_run(db_session, admin, datetime.now(UTC), metrics())

    result = assistant_metric_trends(assistant_type="quality", _=admin, db=db_session)

    assert result["assistant_type"] == "quality"
    assert {item["assistant_type"] for item in result["items"]} == {"quality"}


def test_trends_api_supports_metadata_and_rerank_filters(db_session) -> None:
    admin = make_user(db_session, "trend-mode-admin")
    now = datetime.now(UTC)
    make_run(db_session, admin, now - timedelta(days=1), metrics(hit_at_1=0.4), use_metadata_filter=False, use_rerank=False)
    make_run(db_session, admin, now, metrics(hit_at_1=0.9), use_metadata_filter=True, use_rerank=True)

    result = assistant_metric_trends(
        assistant_type="maintenance",
        use_metadata_filter=True,
        use_rerank=True,
        _=admin,
        db=db_session,
    )

    assert len(result["items"]) == 1
    assert result["items"][0]["use_metadata_filter"] is True
    assert result["items"][0]["use_rerank"] is True


def test_non_admin_cannot_access_trend_api() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
