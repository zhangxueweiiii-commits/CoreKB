import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import generate_improvements, get_improvement, improvement_annotations, update_improvement
from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_improvement import (
    EvaluationImprovementItemCaseResult,
    EvaluationImprovementRelationSource,
    EvaluationImprovementStatus,
)
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.user import User, UserRole
from app.schemas.evaluation import ImprovementGenerateRequest, ImprovementUpdateRequest
from app.services.evaluation_improvement_service import EvaluationImprovementService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def failed_case(
    case_id: str,
    assistant_type: str = "maintenance",
    failure_reason: str = "no_citation",
    suggested_fix_type: str = "prompt",
    expected_metadata: dict | None = None,
    hit_at_1: bool = False,
    hit_at_5: bool = False,
) -> dict:
    return {
        "id": case_id,
        "assistant_type": assistant_type,
        "category": assistant_type,
        "query": "A200 E12",
        "passed": False,
        "citation_present": False,
        "keyword_match_rate": 0.0,
        "metadata_match_rate": 0.0,
        "hit_at_1": hit_at_1,
        "hit_at_3": False,
        "hit_at_5": hit_at_5,
        "expected_document": "A200维修手册",
        "actual_top_documents": ["B300维修手册.txt"],
        "expected_metadata": expected_metadata or {},
        "used_metadata_filter": {},
        "failure_reason": failure_reason,
        "failure_detail": "detail",
        "suggested_fix_type": suggested_fix_type,
    }


def make_run(db, user: User, failed_cases: list[dict]) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=len(failed_cases),
        metrics={},
        failed_cases=failed_cases,
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def make_run_with_case_result(db, user: User, case_id: str = "case_1") -> tuple[EvaluationRun, EvaluationCaseResult]:
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
        expected_document="A200 manual",
        expected_keywords=["E12"],
        expected_metadata={"equipment_model": "A200"},
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
            **failed_case(case_id, failure_reason="metadata_mismatch", suggested_fix_type="metadata_filter"),
            "case_result_id": str(case_result.id),
            "expected_metadata": {"equipment_model": "A200"},
        }
    ]
    db.commit()
    db.refresh(run)
    db.refresh(case_result)
    return run, case_result


def add_annotation(db, user: User, case_result: EvaluationCaseResult) -> EvaluationCaseAnnotation:
    annotation = EvaluationCaseAnnotation(
        evaluation_case_result_id=case_result.id,
        human_judgement="system_partially_correct",
        human_root_cause="document_metadata",
        human_fix_type="update_metadata",
        handling_status="planned",
        handling_notes="needs metadata fix",
        annotated_by=user.id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


def test_summarize_failed_cases_groups_by_fix_type(db_session) -> None:
    admin = make_user(db_session, "improve-admin")
    run = make_run(
        db_session,
        admin,
        [
            failed_case("case_1", suggested_fix_type="prompt"),
            failed_case("case_2", assistant_type="quality", suggested_fix_type="rerank"),
        ],
    )

    summary = EvaluationImprovementService(db_session).summarize_failed_cases(run.id)

    assert summary["total_failed_cases"] == 2
    assert len(summary["by_fix_type"]["prompt"]) == 1
    assert len(summary["by_assistant_type"]["quality"]) == 1


def test_prompt_failure_generates_prompt_improvement_item(db_session) -> None:
    admin = make_user(db_session, "prompt-admin")
    run = make_run(db_session, admin, [failed_case("case_1", failure_reason="no_citation")])

    items = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)

    assert len(items) == 1
    assert items[0].fix_type == "prompt"
    assert items[0].affected_case_ids == ["case_1"]
    assert "引用" in items[0].suggested_action


def test_metadata_mismatch_generates_metadata_improvement_item(db_session) -> None:
    admin = make_user(db_session, "metadata-admin")
    run = make_run(
        db_session,
        admin,
        [
            failed_case(
                "case_1",
                failure_reason="metadata_mismatch",
                suggested_fix_type="document_metadata",
                expected_metadata={"equipment_model": "A200"},
            )
        ],
    )

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    assert item.fix_type in {"metadata_filter", "document_metadata"}
    assert "metadata" in item.suggested_action


def test_low_mrr_generates_rerank_item(db_session) -> None:
    admin = make_user(db_session, "rerank-admin")
    run = make_run(
        db_session,
        admin,
        [failed_case("case_1", failure_reason="low_mrr", suggested_fix_type="rerank", hit_at_5=True)],
    )

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    assert item.fix_type == "rerank"
    assert "rerank_top_n" in item.suggested_action


def test_keyword_missing_generates_chunking_item(db_session) -> None:
    admin = make_user(db_session, "chunking-admin")
    run = make_run(
        db_session,
        admin,
        [failed_case("case_1", failure_reason="keyword_missing", suggested_fix_type="chunking")],
    )

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    assert item.fix_type == "chunking"
    assert "chunk" in item.suggested_action


def test_improvement_priority_calculation() -> None:
    low = [failed_case("case_1", failure_reason="keyword_missing")]
    high_by_count = [failed_case(f"case_{index}", failure_reason="keyword_missing") for index in range(3)]
    high_by_risk = [failed_case("case_risk", failure_reason="answered_should_no_answer")]

    assert EvaluationImprovementService.calculate_fix_priority(low).value == "low"
    assert EvaluationImprovementService.calculate_fix_priority(high_by_count).value == "high"
    assert EvaluationImprovementService.calculate_fix_priority(high_by_risk).value == "high"


def test_repeated_generate_does_not_duplicate_and_force_regenerates(db_session) -> None:
    admin = make_user(db_session, "force-admin")
    run = make_run(db_session, admin, [failed_case("case_1")])
    service = EvaluationImprovementService(db_session)

    first = service.generate_improvement_items(run.id, admin)
    second = service.generate_improvement_items(run.id, admin)
    forced = service.generate_improvement_items(run.id, admin, force=True)

    assert len(first) == 1
    assert [item.id for item in second] == [item.id for item in first]
    assert len(forced) == 1
    assert forced[0].id != first[0].id


def test_generate_improvement_creates_case_result_link(db_session) -> None:
    admin = make_user(db_session, "link-admin")
    run, case_result = make_run_with_case_result(db_session, admin)

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]
    link = db_session.query(EvaluationImprovementItemCaseResult).filter_by(
        improvement_item_id=item.id,
        evaluation_case_result_id=case_result.id,
    ).one()

    assert link.relation_source == EvaluationImprovementRelationSource.system_rule


def test_repeated_generate_does_not_duplicate_case_result_links(db_session) -> None:
    admin = make_user(db_session, "link-repeat-admin")
    run, case_result = make_run_with_case_result(db_session, admin)
    service = EvaluationImprovementService(db_session)

    item = service.generate_improvement_items(run.id, admin)[0]
    service.generate_improvement_items(run.id, admin)

    count = db_session.query(EvaluationImprovementItemCaseResult).filter_by(
        improvement_item_id=item.id,
        evaluation_case_result_id=case_result.id,
    ).count()
    assert count == 1


def test_generate_link_uses_human_annotation_source(db_session) -> None:
    admin = make_user(db_session, "link-human-admin")
    run, case_result = make_run_with_case_result(db_session, admin)
    add_annotation(db_session, admin, case_result)

    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]
    link = db_session.query(EvaluationImprovementItemCaseResult).filter_by(
        improvement_item_id=item.id,
        evaluation_case_result_id=case_result.id,
    ).one()

    assert item.source == "human_annotation"
    assert link.relation_source == EvaluationImprovementRelationSource.human_annotation


def test_improvement_detail_returns_related_annotations(db_session) -> None:
    admin = make_user(db_session, "detail-admin")
    run, case_result = make_run_with_case_result(db_session, admin)
    add_annotation(db_session, admin, case_result)
    item = EvaluationImprovementService(db_session).generate_improvement_items(run.id, admin)[0]

    detail = get_improvement(item.id, admin, db_session)
    annotations = improvement_annotations(item.id, _=admin, db=db_session)

    assert detail["id"] == item.id
    assert detail["related_case_results"][0]["evaluation_case_result_id"] == case_result.id
    assert detail["related_annotations"][0]["evaluation_case_result_id"] == case_result.id
    assert annotations["total"] == 1
    assert annotations["items"][0]["case_id"] == case_result.case_id


def test_improvement_summary_returns_by_fix_type(db_session) -> None:
    admin = make_user(db_session, "summary-admin")
    run = make_run(
        db_session,
        admin,
        [
            failed_case("case_1", suggested_fix_type="prompt"),
            failed_case("case_2", assistant_type="quality", suggested_fix_type="rerank", failure_reason="low_mrr"),
        ],
    )
    service = EvaluationImprovementService(db_session)
    service.generate_improvement_items(run.id, admin)

    summary = service.summary()

    assert summary["total_open"] == 2
    assert summary["by_fix_type"]["prompt"] == 1
    assert summary["by_fix_type"]["rerank"] == 1


def test_patch_can_update_status(db_session) -> None:
    admin = make_user(db_session, "patch-admin")
    run = make_run(db_session, admin, [failed_case("case_1")])
    item = generate_improvements(ImprovementGenerateRequest(evaluation_run_id=run.id), admin, db_session)[0]

    updated = update_improvement(
        item.id,
        ImprovementUpdateRequest(status="resolved", suggested_action="done"),
        admin,
        db_session,
    )

    assert updated.status == EvaluationImprovementStatus.resolved
    assert updated.suggested_action == "done"
    assert updated.resolved_by == admin.id
    assert updated.resolved_at is not None


def test_non_admin_cannot_generate_or_modify_improvement_items() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
