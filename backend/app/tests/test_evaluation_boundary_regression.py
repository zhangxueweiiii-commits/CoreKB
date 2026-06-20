import uuid

from app.api.routes.evaluation import (
    batch_update_failure_triage_notes,
    compare_evaluation_case,
    get_evaluation_case_result,
)
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_improvement import EvaluationImprovementItem, EvaluationImprovementItemCaseResult
from app.models.evaluation_regression import EvaluationRegression
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.evaluation_triage_note import EvaluationFailureTriageNote
from app.models.index_job import IndexJob, IndexJobItem
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.evaluation import EvaluationFailureTriageBatchUpdateRequest


PRODUCTION_BOUNDARY_MODELS = [
    DocumentMetadataSuggestion,
    IndexJob,
    IndexJobItem,
    EvaluationCaseAnnotation,
    EvaluationImprovementItem,
    EvaluationImprovementItemCaseResult,
    EvaluationRegression,
]


def make_user(db, username: str = "boundary-admin") -> User:
    user = User(username=username, password_hash="x", role=UserRole.admin, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_document(db, user: User) -> Document:
    kb = KnowledgeBase(name="Boundary KB", description="Boundary test", owner_id=user.id)
    db.add(kb)
    db.flush()
    document = Document(
        knowledge_base_id=kb.id,
        filename="A200 manual.pdf",
        file_path="uploads/a200.pdf",
        file_type="pdf",
        file_size=123,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta={"equipment_model": "A200", "fault_code": "E12", "version": "V1.0"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def make_run(db, user: User, label: str) -> EvaluationRun:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={"hit_at_1": 0.0, "hit_at_3": 1.0, "mrr": 0.5},
        failed_cases=[],
        run_label=label,
        config_snapshot={
            "eval_type": "assistant",
            "assistant_types": ["maintenance"],
            "use_metadata_filter": True,
            "use_rerank": True,
            "rerank_top_n": 20,
            "evaluation_case_set_signature": "boundary-test",
        },
        created_by=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def make_case_result(
    db,
    run: EvaluationRun,
    case_id: str = "maintenance_boundary_001",
    passed: bool = False,
) -> EvaluationCaseResult:
    case_result = EvaluationCaseResult(
        evaluation_run_id=run.id,
        case_id=case_id,
        assistant_type="maintenance",
        query="A200 E12 troubleshooting",
        expected_document="A200 manual",
        expected_keywords=["E12"],
        expected_metadata={"equipment_model": "A200", "fault_code": "E12"},
        should_have_answer=True,
        passed=passed,
        failure_reason=None if passed else "metadata_mismatch",
        suggested_fix_type=None if passed else "document_metadata",
        used_metadata_filter={"equipment_model": "A200", "fault_code": "E12"},
        use_rerank=True,
        rerank_applied=True,
        answer_excerpt="Check E12 wiring according to the saved evaluation snapshot.",
        citations=[{"chunk_id": "chunk-1", "quote": "E12 wiring"}],
        retrieved_results=[
            {
                "rank": 1,
                "document_id": str(uuid.uuid4()),
                "document_name": "A200 manual",
                "chunk_id": "chunk-1",
                "chunk_excerpt": "E12 wiring check",
                "chunk_metadata": {"equipment_model": "A200"},
                "vector_score": 0.81,
                "rerank_score": 0.91,
                "final_score": 0.91,
            }
        ],
    )
    db.add(case_result)
    db.flush()
    run.failed_cases = [] if passed else [{"id": case_id, "case_result_id": str(case_result.id)}]
    db.commit()
    db.refresh(case_result)
    return case_result


def boundary_counts(db) -> dict[str, int]:
    return {model.__name__: db.query(model).count() for model in PRODUCTION_BOUNDARY_MODELS}


def assert_document_metadata_unchanged(document: Document, expected: dict) -> None:
    assert document.meta == expected


def test_case_drilldown_reads_snapshot_without_mutating_production_boundaries(db_session) -> None:
    admin = make_user(db_session, "boundary-drilldown-admin")
    document = make_document(db_session, admin)
    original_meta = dict(document.meta)
    run = make_run(db_session, admin, "before")
    case_result = make_case_result(db_session, run)
    before_counts = boundary_counts(db_session)

    detail = get_evaluation_case_result(case_result.id, admin, db_session)

    db_session.refresh(document)
    assert detail["case_result_id"] == case_result.id
    assert detail["retrieved_results"][0]["chunk_excerpt"] == "E12 wiring check"
    assert_document_metadata_unchanged(document, original_meta)
    assert boundary_counts(db_session) == before_counts
    assert db_session.query(EvaluationFailureTriageNote).count() == 0


def test_compare_case_missing_snapshot_returns_unavailable_without_rerun_or_new_records(db_session) -> None:
    admin = make_user(db_session, "boundary-compare-admin")
    document = make_document(db_session, admin)
    original_meta = dict(document.meta)
    before_run = make_run(db_session, admin, "before")
    after_run = make_run(db_session, admin, "after")
    make_case_result(db_session, before_run, case_id="missing_after_case")
    case_count_before = db_session.query(EvaluationCaseResult).count()
    boundary_before = boundary_counts(db_session)

    result = compare_evaluation_case("missing_after_case", before_run.id, after_run.id, admin, db_session)

    db_session.refresh(document)
    assert result["comparison"]["status"] == "unavailable"
    assert result["after"] is None
    assert db_session.query(EvaluationCaseResult).count() == case_count_before
    assert_document_metadata_unchanged(document, original_meta)
    assert boundary_counts(db_session) == boundary_before
    assert db_session.query(EvaluationFailureTriageNote).count() == 0


def test_batch_triage_only_writes_triage_notes_not_structured_or_production_records(db_session) -> None:
    admin = make_user(db_session, "boundary-batch-admin")
    document = make_document(db_session, admin)
    original_meta = dict(document.meta)
    run = make_run(db_session, admin, "batch")
    first_case = make_case_result(db_session, run, case_id="batch_case_one")
    second_case = make_case_result(db_session, run, case_id="batch_case_two")
    boundary_before = boundary_counts(db_session)

    notes = batch_update_failure_triage_notes(
        EvaluationFailureTriageBatchUpdateRequest(
            evaluation_case_result_ids=[first_case.id, second_case.id],
            triage_status="reviewing",
            note="Boundary triage note only.",
            note_mode="replace",
        ),
        admin,
        db_session,
    )

    db_session.refresh(document)
    assert len(notes) == 2
    assert db_session.query(EvaluationFailureTriageNote).count() == 2
    assert {note.evaluation_case_result_id for note in notes} == {first_case.id, second_case.id}
    assert_document_metadata_unchanged(document, original_meta)
    assert boundary_counts(db_session) == boundary_before
