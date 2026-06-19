import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import (
    get_evaluation_case_result,
    list_case_annotations,
    upsert_case_annotation,
)
from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_improvement import EvaluationImprovementItemCaseResult
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.schemas.evaluation import EvaluationCaseAnnotationCreate
from app.services.evaluation_improvement_service import EvaluationImprovementService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_case_result(db, user: User, case_id: str = "case_1") -> tuple[EvaluationRun, EvaluationCaseResult]:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={},
        failed_cases=[],
        created_by=user.id,
    )
    db.add(run)
    db.flush()
    case_result = EvaluationCaseResult(
        evaluation_run_id=run.id,
        case_id=case_id,
        assistant_type="maintenance",
        query="A200 E12",
        expected_document="A200维修手册",
        expected_keywords=["E12"],
        expected_metadata={"equipment_model": "A200", "fault_code": "E12"},
        should_have_answer=True,
        passed=False,
        failure_reason="metadata_mismatch",
        suggested_fix_type="metadata_filter",
        used_metadata_filter={},
        use_rerank=True,
        rerank_applied=True,
        answer_excerpt="answer",
        citations=[],
        retrieved_results=[],
    )
    db.add(case_result)
    db.flush()
    run.failed_cases = [
        {
            "id": case_id,
            "assistant_type": "maintenance",
            "failure_reason": "metadata_mismatch",
            "suggested_fix_type": "metadata_filter",
            "expected_metadata": {"equipment_model": "A200"},
            "case_result_id": str(case_result.id),
        }
    ]
    db.commit()
    db.refresh(run)
    db.refresh(case_result)
    return run, case_result


def annotation_payload(**overrides) -> EvaluationCaseAnnotationCreate:
    data = {
        "human_judgement": "system_partially_correct",
        "human_root_cause": "document_metadata",
        "human_fix_type": "update_metadata",
        "handling_status": "planned",
        "handling_notes": "A200 fixture 缺少 fault_code=E12，补齐后重建索引。",
    }
    data.update(overrides)
    return EvaluationCaseAnnotationCreate(**data)


def test_admin_can_create_case_annotation(db_session) -> None:
    admin = make_user(db_session, "annotation-admin")
    _, case_result = make_case_result(db_session, admin)

    annotation = upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)

    assert annotation.evaluation_case_result_id == case_result.id
    assert annotation.human_root_cause.value == "document_metadata"
    assert annotation.handling_status.value == "planned"
    assert annotation.annotated_by == admin.id


def test_duplicate_create_updates_existing_annotation(db_session) -> None:
    admin = make_user(db_session, "annotation-update-admin")
    _, case_result = make_case_result(db_session, admin)

    first = upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)
    second = upsert_case_annotation(
        case_result.id,
        annotation_payload(human_root_cause="prompt", human_fix_type="update_prompt", handling_status="investigating"),
        admin,
        db_session,
    )

    rows = db_session.query(EvaluationCaseAnnotation).filter_by(evaluation_case_result_id=case_result.id).all()
    assert len(rows) == 1
    assert second.id == first.id
    assert second.human_root_cause.value == "prompt"
    assert second.handling_status.value == "investigating"


def test_non_admin_cannot_access_annotation_api() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403


def test_invalid_human_judgement_returns_bad_request(db_session) -> None:
    admin = make_user(db_session, "annotation-invalid-admin")
    _, case_result = make_case_result(db_session, admin)

    with pytest.raises(HTTPException) as exc:
        upsert_case_annotation(
            case_result.id,
            annotation_payload(human_judgement="bad_value"),
            admin,
            db_session,
        )

    assert exc.value.status_code == 400


def test_annotation_is_returned_in_drilldown_detail(db_session) -> None:
    admin = make_user(db_session, "annotation-drill-admin")
    _, case_result = make_case_result(db_session, admin)
    annotation = upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)

    detail = get_evaluation_case_result(case_result.id, admin, db_session)

    assert detail["annotation"]["id"] == annotation.id
    assert detail["annotation"]["human_fix_type"] == "update_metadata"


def test_improvement_generation_prefers_human_annotation(db_session) -> None:
    admin = make_user(db_session, "annotation-improvement-admin")
    run, case_result = make_case_result(db_session, admin)
    upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    assert item.fix_type == "document_metadata"
    assert item.source == "human_annotation"
    assert item.annotation_count == 1
    assert item.main_failure_reasons == ["document_metadata"]


def test_improvement_generation_uses_system_rule_without_annotation(db_session) -> None:
    admin = make_user(db_session, "annotation-system-rule-admin")
    run, _ = make_case_result(db_session, admin)

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    assert item.fix_type == "document_metadata"
    assert item.source == "system_rule"
    assert item.annotation_count == 0


def test_annotation_list_filters_by_handling_status(db_session) -> None:
    admin = make_user(db_session, "annotation-list-admin")
    _, case_result = make_case_result(db_session, admin, "case_planned")
    _, case_result_2 = make_case_result(db_session, admin, "case_open")
    upsert_case_annotation(case_result.id, annotation_payload(handling_status="planned"), admin, db_session)
    upsert_case_annotation(case_result_2.id, annotation_payload(handling_status="open"), admin, db_session)

    result = list_case_annotations(
        handling_status="planned",
        _=admin,
        db=db_session,
    )

    assert result["total"] == 1
    assert result["items"][0]["evaluation_case_result_id"] == case_result.id
    assert result["items"][0]["case_id"] == "case_planned"


def test_annotation_list_filters_by_root_cause_and_fix_type(db_session) -> None:
    admin = make_user(db_session, "annotation-filter-admin")
    _, case_result = make_case_result(db_session, admin, "case_metadata")
    _, case_result_2 = make_case_result(db_session, admin, "case_prompt")
    upsert_case_annotation(case_result.id, annotation_payload(human_root_cause="document_metadata", human_fix_type="update_metadata"), admin, db_session)
    upsert_case_annotation(case_result_2.id, annotation_payload(human_root_cause="prompt", human_fix_type="update_prompt"), admin, db_session)

    by_root = list_case_annotations(human_root_cause="document_metadata", _=admin, db=db_session)
    by_fix = list_case_annotations(human_fix_type="update_prompt", _=admin, db=db_session)

    assert by_root["total"] == 1
    assert by_root["items"][0]["case_id"] == "case_metadata"
    assert by_fix["total"] == 1
    assert by_fix["items"][0]["case_id"] == "case_prompt"


def test_annotation_list_filters_by_assistant_type_and_run_id(db_session) -> None:
    admin = make_user(db_session, "annotation-run-filter-admin")
    run, case_result = make_case_result(db_session, admin, "case_maintenance")
    run_2, case_result_2 = make_case_result(db_session, admin, "case_quality")
    case_result_2.assistant_type = "quality"
    db_session.commit()
    upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)
    upsert_case_annotation(case_result_2.id, annotation_payload(), admin, db_session)

    by_assistant = list_case_annotations(assistant_type="quality", _=admin, db=db_session)
    by_run = list_case_annotations(evaluation_run_id=run.id, _=admin, db=db_session)

    assert by_assistant["total"] == 1
    assert by_assistant["items"][0]["evaluation_run_id"] == run_2.id
    assert by_run["total"] == 1
    assert by_run["items"][0]["case_id"] == "case_maintenance"


def test_annotation_list_keyword_search_matches_case_query_and_notes(db_session) -> None:
    admin = make_user(db_session, "annotation-keyword-admin")
    _, case_result = make_case_result(db_session, admin, "case_kw_id")
    _, case_result_2 = make_case_result(db_session, admin, "case_other")
    case_result_2.query = "special pump alarm"
    db_session.commit()
    upsert_case_annotation(case_result.id, annotation_payload(handling_notes="needs metadata review"), admin, db_session)
    upsert_case_annotation(case_result_2.id, annotation_payload(), admin, db_session)

    by_case_id = list_case_annotations(keyword="kw_id", _=admin, db=db_session)
    by_query = list_case_annotations(keyword="pump", _=admin, db=db_session)
    by_notes = list_case_annotations(keyword="metadata review", _=admin, db=db_session)

    assert by_case_id["total"] == 1
    assert by_case_id["items"][0]["case_id"] == "case_kw_id"
    assert by_query["total"] == 1
    assert by_query["items"][0]["case_id"] == "case_other"
    assert by_notes["total"] == 1
    assert by_notes["items"][0]["case_id"] == "case_kw_id"


def test_annotation_list_pagination_fields_are_correct(db_session) -> None:
    admin = make_user(db_session, "annotation-page-admin")
    for index in range(3):
        _, case_result = make_case_result(db_session, admin, f"case_page_{index}")
        upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)

    result = list_case_annotations(page=2, page_size=2, _=admin, db=db_session)

    assert result["total"] == 3
    assert result["page"] == 2
    assert result["page_size"] == 2
    assert result["pages"] == 2
    assert len(result["items"]) == 1


def test_annotation_list_filters_by_improvement_item_id(db_session) -> None:
    admin = make_user(db_session, "annotation-improvement-filter-admin")
    run, case_result = make_case_result(db_session, admin, "case_improvement")
    upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)
    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    result = list_case_annotations(improvement_item_id=item.id, _=admin, db=db_session)

    assert result["total"] == 1
    assert result["items"][0]["case_id"] == "case_improvement"
    assert result["items"][0]["related_improvement_items"][0]["id"] == item.id


def test_annotation_list_filters_by_improvement_status_and_regression_status(db_session) -> None:
    admin = make_user(db_session, "annotation-improvement-status-admin")
    run, case_result = make_case_result(db_session, admin, "case_status")
    upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)
    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    by_status = list_case_annotations(improvement_status="open", _=admin, db=db_session)
    by_regression = list_case_annotations(regression_status="unverified", _=admin, db=db_session)

    assert by_status["total"] == 1
    assert by_status["items"][0]["related_improvement_items"][0]["status"] == "open"
    assert by_regression["total"] == 1
    assert by_regression["items"][0]["related_improvement_items"][0]["regression_status"] == "unverified"
    assert db_session.query(EvaluationImprovementItemCaseResult).filter_by(improvement_item_id=item.id).count() == 1


def test_ignoring_annotation_does_not_delete_improvement_item(db_session) -> None:
    admin = make_user(db_session, "annotation-ignore-admin")
    run, case_result = make_case_result(db_session, admin, "case_ignore")
    upsert_case_annotation(case_result.id, annotation_payload(), admin, db_session)
    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    upsert_case_annotation(case_result.id, annotation_payload(handling_status="ignored"), admin, db_session)

    result = list_case_annotations(improvement_item_id=item.id, _=admin, db=db_session)
    assert result["total"] == 1
    assert result["items"][0]["handling_status"] == "ignored"
    assert result["items"][0]["related_improvement_items"][0]["id"] == item.id
