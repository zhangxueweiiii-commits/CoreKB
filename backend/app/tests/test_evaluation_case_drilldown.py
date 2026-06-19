import json
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import compare_evaluation_case
from app.models.document import Document, DocumentStatus
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.assistant import AssistantChatResponse
from app.schemas.chat import Citation
from app.services.evaluation_case_drilldown_service import EvaluationCaseDrilldownService
from app.services.evaluation_run_metadata_service import build_assistant_config_snapshot
from app.services.evaluation_service import EvaluationService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(name="CoreKB Evaluation KB", owner_id=owner.id, visibility="private")
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, role=KBPermissionRole.owner, created_by=owner.id))
    db.commit()
    db.refresh(kb)
    return kb


def make_indexed_document(db, kb: KnowledgeBase, tmp_path: Path) -> None:
    db.add(
        Document(
            knowledge_base_id=kb.id,
            filename="MaintenanceGuide.txt",
            file_path=str(tmp_path / "MaintenanceGuide.txt"),
            file_type="txt",
            file_size=1,
            status=DocumentStatus.indexed,
            meta={"document_title": "MaintenanceGuide"},
        )
    )
    db.commit()


def write_cases(tmp_path: Path) -> Path:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "case_pass",
                    "category": "maintenance",
                    "assistant_type": "maintenance",
                    "query": "A200 E12",
                    "expected_document": "MaintenanceGuide",
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200"},
                    "should_have_answer": True,
                },
                {
                    "id": "case_fail",
                    "category": "maintenance",
                    "assistant_type": "maintenance",
                    "query": "A200 E99",
                    "expected_document": "MaintenanceGuide",
                    "expected_keywords": ["E99"],
                    "expected_metadata": {"equipment_model": "A200"},
                    "should_have_answer": True,
                },
            ]
        ),
        encoding="utf-8",
    )
    return cases_path


@pytest.mark.asyncio
async def test_evaluation_run_creates_all_case_result_snapshots(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "drill-admin")
    kb = make_kb(db_session, admin)
    make_indexed_document(db_session, kb, tmp_path)
    cases_path = write_cases(tmp_path)
    long_chunk = "E12 " + ("x" * 1500)

    class FakeAssistantService:
        async def chat(self, db, user, assistant_type, payload):
            if "E99" in payload.query:
                return AssistantChatResponse(
                    assistant_type=assistant_type,
                    answer="No citation",
                    citations=[],
                    sources=[],
                    used_metadata_filter=payload.metadata_filter or {},
                    use_rerank=payload.use_rerank,
                    rerank_applied=True,
                    no_answer_detected=False,
                    conversation_id=uuid.uuid4(),
                    retrieved_results=[],
                )
            citation = Citation(filename="MaintenanceGuide.txt", chunk_id=uuid.uuid4(), quote="E12 wiring")
            return AssistantChatResponse(
                assistant_type=assistant_type,
                answer="Check E12 wiring",
                citations=[citation],
                sources=[citation],
                used_metadata_filter=payload.metadata_filter or {},
                use_rerank=payload.use_rerank,
                rerank_applied=True,
                no_answer_detected=False,
                conversation_id=uuid.uuid4(),
                retrieved_results=[
                    {
                        "rank": 1,
                        "document_id": str(uuid.uuid4()),
                        "document_name": "MaintenanceGuide.txt",
                        "chunk_id": str(uuid.uuid4()),
                        "chunk_excerpt": long_chunk,
                        "chunk_metadata": {"equipment_model": "A200"},
                        "vector_score": 0.7,
                        "rerank_score": 0.9,
                        "final_score": 0.9,
                        "citation": citation.model_dump(mode="json"),
                    }
                ],
            )

    result = await EvaluationService(assistant_service=FakeAssistantService()).run_assistant_eval(
        db_session,
        admin,
        cases_path=cases_path,
        use_rerank=True,
    )

    rows = db_session.query(EvaluationCaseResult).filter_by(evaluation_run_id=result.run_id).all()
    assert len(rows) == 2
    saved = next(row for row in rows if row.case_id == "case_pass")
    assert saved.retrieved_results[0]["rank"] == 1
    assert saved.retrieved_results[0]["document_name"] == "MaintenanceGuide.txt"
    assert saved.retrieved_results[0]["chunk_metadata"] == {"equipment_model": "A200"}
    assert saved.retrieved_results[0]["vector_score"] == 0.7
    assert len(saved.retrieved_results[0]["chunk_excerpt"]) == 1200
    assert "x" * 1300 not in saved.retrieved_results[0]["chunk_excerpt"]
    assert result.failed_cases[0].case_result_id is not None


def make_run_with_snapshot(db, user: User, case_id: str, passed: bool, label: str) -> tuple[EvaluationRun, EvaluationCaseResult]:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={},
        failed_cases=[] if passed else [{"id": case_id, "case_result_id": None}],
        config_snapshot=build_assistant_config_snapshot(True, True, 20, ["maintenance"], "single", "sig", [case_id]),
        run_label=label,
        created_by=user.id,
    )
    db.add(run)
    db.flush()
    row = EvaluationCaseResult(
        evaluation_run_id=run.id,
        case_id=case_id,
        assistant_type="maintenance",
        query="A200 E12",
        expected_document="MaintenanceGuide",
        expected_keywords=["E12"],
        expected_metadata={"equipment_model": "A200"},
        should_have_answer=True,
        passed=passed,
        failure_reason=None if passed else "wrong_document_retrieved",
        suggested_fix_type=None if passed else "metadata_filter",
        used_metadata_filter={"equipment_model": "A200"} if passed else {},
        use_rerank=True,
        rerank_applied=True,
        answer_excerpt="answer",
        citations=[{"filename": "MaintenanceGuide.txt", "chunk_id": str(uuid.uuid4()), "quote": "E12"}] if passed else [],
        retrieved_results=[
            {
                "rank": 1 if passed else 8,
                "document_id": str(uuid.uuid4()),
                "document_name": "MaintenanceGuide.txt" if passed else "Other.txt",
                "chunk_id": str(uuid.uuid4()),
                "chunk_excerpt": "E12 wiring",
                "chunk_metadata": {"equipment_model": "A200"},
                "vector_score": 0.5,
                "rerank_score": 0.8,
                "final_score": 0.8,
                "citation": {},
            }
        ],
    )
    db.add(row)
    db.flush()
    if not passed:
        run.failed_cases = [{"id": case_id, "case_result_id": str(row.id), "failure_reason": row.failure_reason}]
    db.commit()
    db.refresh(run)
    db.refresh(row)
    return run, row


def test_compare_case_api_returns_before_after_snapshots_and_resolved_status(db_session) -> None:
    admin = make_user(db_session, "drill-compare-admin")
    before_run, _ = make_run_with_snapshot(db_session, admin, "case_1", False, "before")
    after_run, after_row = make_run_with_snapshot(db_session, admin, "case_1", True, "after")

    result = compare_evaluation_case("case_1", before_run.id, after_run.id, admin, db_session)

    assert result["before"]["passed"] is False
    assert result["after"]["case_result_id"] == after_row.id
    assert result["comparison"]["status"] == "resolved"
    assert result["comparison"]["metadata_filter_changed"] is True
    assert result["diagnostic_hints"]


def test_compare_case_detects_introduced_failure(db_session) -> None:
    admin = make_user(db_session, "drill-introduced-admin")
    before_run, _ = make_run_with_snapshot(db_session, admin, "case_1", True, "before")
    after_run, _ = make_run_with_snapshot(db_session, admin, "case_1", False, "after")

    result = EvaluationCaseDrilldownService(db_session).compare_case(before_run.id, after_run.id, "case_1")

    assert result["comparison"]["status"] == "introduced_failure"


def test_history_without_snapshot_returns_unavailable_without_rerun(db_session) -> None:
    admin = make_user(db_session, "drill-history-admin")
    before_run = EvaluationRun(eval_type=EvaluationType.assistant, total_cases=1, metrics={}, failed_cases=[])
    after_run = EvaluationRun(eval_type=EvaluationType.assistant, total_cases=1, metrics={}, failed_cases=[])
    db_session.add_all([before_run, after_run])
    db_session.commit()
    db_session.refresh(before_run)
    db_session.refresh(after_run)

    result = EvaluationCaseDrilldownService(db_session).compare_case(before_run.id, after_run.id, "old_case")

    assert result["comparison"]["status"] == "unavailable"
    assert "未保存详细快照" in result["diagnostic_hints"][0]


def test_non_admin_cannot_access_drilldown_api() -> None:
    viewer = User(id=uuid.uuid4(), username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
