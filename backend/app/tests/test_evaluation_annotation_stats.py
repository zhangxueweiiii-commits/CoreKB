import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import annotation_summary
from app.models.evaluation_annotation import (
    EvaluationCaseAnnotation,
    HandlingStatus,
    HumanFixType,
    HumanJudgement,
    HumanRootCause,
)
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.services.evaluation_annotation_stats_service import EvaluationAnnotationStatsService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_run(db, user: User, label: str) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=0,
        metrics={},
        failed_cases=[],
        run_label=label,
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def add_annotation(
    db,
    run: EvaluationRun,
    user: User,
    case_id: str,
    assistant_type: str,
    root_cause: HumanRootCause,
    fix_type: HumanFixType,
    status: HandlingStatus,
) -> EvaluationCaseAnnotation:
    case_result = EvaluationCaseResult(
        evaluation_run_id=run.id,
        case_id=case_id,
        assistant_type=assistant_type,
        query="query",
        expected_document="doc",
        expected_keywords=[],
        expected_metadata={},
        should_have_answer=True,
        passed=False,
        failure_reason="unknown",
        suggested_fix_type="unknown",
        used_metadata_filter={},
        use_rerank=True,
        rerank_applied=True,
        answer_excerpt="answer",
        citations=[],
        retrieved_results=[],
    )
    db.add(case_result)
    db.flush()
    annotation = EvaluationCaseAnnotation(
        evaluation_case_result_id=case_result.id,
        human_judgement=HumanJudgement.system_partially_correct,
        human_root_cause=root_cause,
        human_fix_type=fix_type,
        handling_status=status,
        handling_notes="notes",
        annotated_by=user.id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


def seed_annotations(db, user: User) -> tuple[EvaluationRun, EvaluationRun]:
    run_1 = make_run(db, user, "run-1")
    run_2 = make_run(db, user, "run-2")
    add_annotation(
        db,
        run_1,
        user,
        "case_1",
        "maintenance",
        HumanRootCause.document_metadata,
        HumanFixType.update_metadata,
        HandlingStatus.open,
    )
    add_annotation(
        db,
        run_1,
        user,
        "case_2",
        "maintenance",
        HumanRootCause.document_metadata,
        HumanFixType.update_metadata,
        HandlingStatus.open,
    )
    add_annotation(
        db,
        run_1,
        user,
        "case_3",
        "maintenance",
        HumanRootCause.chunking,
        HumanFixType.update_chunking,
        HandlingStatus.open,
    )
    add_annotation(
        db,
        run_1,
        user,
        "case_4",
        "quality",
        HumanRootCause.prompt,
        HumanFixType.update_prompt,
        HandlingStatus.resolved,
    )
    add_annotation(
        db,
        run_2,
        user,
        "case_5",
        "material",
        HumanRootCause.document_metadata,
        HumanFixType.update_metadata,
        HandlingStatus.planned,
    )
    return run_1, run_2


def test_root_cause_fix_type_and_handling_status_stats_are_correct(db_session) -> None:
    admin = make_user(db_session, "stats-admin")
    seed_annotations(db_session, admin)

    summary = EvaluationAnnotationStatsService(db_session).get_annotation_summary()

    assert summary["total_annotations"] == 5
    assert summary["by_root_cause"][0]["key"] == "document_metadata"
    assert summary["by_root_cause"][0]["count"] == 3
    assert summary["by_fix_type"][0]["key"] == "update_metadata"
    assert summary["by_fix_type"][0]["count"] == 3
    assert summary["by_handling_status"][0]["key"] == "open"
    assert summary["by_handling_status"][0]["count"] == 3


def test_assistant_type_filter_works(db_session) -> None:
    admin = make_user(db_session, "stats-assistant-admin")
    seed_annotations(db_session, admin)

    summary = EvaluationAnnotationStatsService(db_session).get_annotation_summary(assistant_type="maintenance")

    assert summary["total_annotations"] == 3
    assert summary["by_assistant_type"] == [{"key": "maintenance", "label": "维修助手", "count": 3}]


def test_evaluation_run_id_filter_works(db_session) -> None:
    admin = make_user(db_session, "stats-run-admin")
    run_1, _ = seed_annotations(db_session, admin)

    summary = EvaluationAnnotationStatsService(db_session).get_annotation_summary(evaluation_run_id=run_1.id)

    assert summary["total_annotations"] == 4
    assert {item["key"] for item in summary["by_assistant_type"]} == {"maintenance", "quality"}


def test_percentage_is_calculated_correctly(db_session) -> None:
    admin = make_user(db_session, "stats-percent-admin")
    seed_annotations(db_session, admin)

    summary = EvaluationAnnotationStatsService(db_session).get_annotation_summary()

    document_metadata = next(item for item in summary["by_root_cause"] if item["key"] == "document_metadata")
    assert document_metadata["percentage"] == pytest.approx(0.6)


def test_open_priority_items_are_sorted_by_count(db_session) -> None:
    admin = make_user(db_session, "stats-priority-admin")
    seed_annotations(db_session, admin)

    items = EvaluationAnnotationStatsService(db_session).get_annotation_summary()["open_priority_items"]

    assert items[0]["root_cause"] == "document_metadata"
    assert items[0]["fix_type"] == "update_metadata"
    assert items[0]["assistant_type"] == "maintenance"
    assert items[0]["count"] == 2


def test_document_metadata_top_root_cause_returns_metadata_action(db_session) -> None:
    admin = make_user(db_session, "stats-action-admin")
    seed_annotations(db_session, admin)

    top_root = EvaluationAnnotationStatsService(db_session).get_annotation_summary()["by_root_cause"][0]

    assert top_root["key"] == "document_metadata"
    assert "元数据" in top_root["recommended_action"]


def test_summary_api_is_admin_only() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403


def test_annotation_summary_route_returns_summary(db_session) -> None:
    admin = make_user(db_session, "stats-route-admin")
    seed_annotations(db_session, admin)

    summary = annotation_summary(None, "maintenance", None, None, None, admin, db_session)

    assert summary["total_annotations"] == 3
    assert summary["by_root_cause"][0]["key"] == "document_metadata"
