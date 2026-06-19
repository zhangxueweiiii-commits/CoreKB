import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.routes.evaluation import run_retrieval_evaluation
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.index_job import IndexJob
from app.models.user import User, UserRole
from app.schemas.evaluation import EvalCase, EvalCaseResult
from app.services.evaluation_service import EvaluationService
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet
from scripts.import_evaluation_fixtures import EvaluationFixtureImporter, scan_fixture_documents


FIXTURES = Path(__file__).parent / "fixtures"
EVAL_CASES = FIXTURES / "expected" / "eval_cases.json"


def make_user(db, username: str, role: UserRole = UserRole.viewer) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_fixture_files_can_be_scanned() -> None:
    files = scan_fixture_documents(FIXTURES / "documents")
    names = {path.name for path in files}

    assert {"maintenance_A200.txt", "quality_standard.csv", "sop_checklist.docx", "material_parameters.xlsx"} <= names


def test_duplicate_import_does_not_create_duplicate_documents(db_session, tmp_path) -> None:
    make_user(db_session, "admin", UserRole.admin)
    settings = SimpleNamespace(
        evaluation_fixtures_dir=FIXTURES / "documents",
        upload_dir=tmp_path / "uploads",
        evaluation_kb_name="CoreKB Evaluation KB",
    )
    enqueued = []
    importer = EvaluationFixtureImporter(db_session, settings=settings, enqueue_job=enqueued.append, delete_vectors=False)

    first = importer.import_fixtures()
    second = importer.import_fixtures()

    assert first.imported_count >= 5
    assert second.imported_count == 0
    assert second.skipped_count == first.imported_count
    assert db_session.query(Document).count() == first.imported_count
    assert len(enqueued) == first.imported_count


def test_force_reimports_and_triggers_reindex(db_session, tmp_path) -> None:
    make_user(db_session, "admin", UserRole.admin)
    settings = SimpleNamespace(
        evaluation_fixtures_dir=FIXTURES / "documents",
        upload_dir=tmp_path / "uploads",
        evaluation_kb_name="CoreKB Evaluation KB",
    )
    enqueued = []
    importer = EvaluationFixtureImporter(db_session, settings=settings, enqueue_job=enqueued.append, delete_vectors=False)
    importer.import_fixtures()
    initial_document_count = db_session.query(Document).count()

    forced = importer.import_fixtures(force=True)

    assert forced.imported_count == initial_document_count
    assert db_session.query(Document).count() == initial_document_count
    assert db_session.query(IndexJob).count() == initial_document_count * 2
    assert len(enqueued) == initial_document_count * 2


def test_reset_clears_evaluation_kb_then_reimports(db_session, tmp_path) -> None:
    make_user(db_session, "admin", UserRole.admin)
    settings = SimpleNamespace(
        evaluation_fixtures_dir=FIXTURES / "documents",
        upload_dir=tmp_path / "uploads",
        evaluation_kb_name="CoreKB Evaluation KB",
    )
    importer = EvaluationFixtureImporter(db_session, settings=settings, enqueue_job=lambda _: None, delete_vectors=False)
    first = importer.import_fixtures()
    first_ids = set(first.document_ids)

    reset = importer.import_fixtures(reset=True)

    assert reset.imported_count == first.imported_count
    assert set(reset.document_ids).isdisjoint(first_ids)
    assert db_session.query(Document).count() == first.imported_count


def create_eval_kb(db, owner: User, name: str = "CoreKB Evaluation KB") -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description="Evaluation",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, role=KBPermissionRole.owner, created_by=owner.id))
    db.commit()
    db.refresh(kb)
    return kb


def test_evaluation_service_detects_missing_documents(db_session, monkeypatch) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)
    create_eval_kb(db_session, admin)
    monkeypatch.setattr(
        "app.services.evaluation_service.get_settings",
        lambda: SimpleNamespace(evaluation_kb_name="CoreKB Evaluation KB"),
    )

    readiness = EvaluationService().ensure_evaluation_kb_ready(db_session, EVAL_CASES)

    assert readiness.evaluation_kb_ready is False
    assert "A200维修手册" in readiness.missing_documents


def test_evaluation_service_detects_unindexed_documents(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)
    kb = create_eval_kb(db_session, admin)
    document = Document(
        knowledge_base_id=kb.id,
        filename="maintenance_A200.txt",
        file_path=str(tmp_path / "maintenance_A200.txt"),
        file_type="txt",
        file_size=1,
        status=DocumentStatus.uploaded,
        meta={"document_title": "A200维修手册"},
    )
    db_session.add(document)
    db_session.commit()
    monkeypatch.setattr(
        "app.services.evaluation_service.get_settings",
        lambda: SimpleNamespace(evaluation_kb_name="CoreKB Evaluation KB"),
    )

    readiness = EvaluationService().ensure_evaluation_kb_ready(
        db_session,
        FIXTURES / "expected" / "eval_cases.json",
    )

    assert readiness.evaluation_kb_ready is False
    assert "A200维修手册" in readiness.unindexed_documents


def chunk(
    filename: str,
    text: str,
    score: float = 0.9,
    metadata: dict | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_text=text,
        filename=filename,
        page_number=None,
        score=score,
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        metadata=metadata or {},
    )


class StaticRetrieval:
    def __init__(self, results):
        self.results = results

    async def search_with_options(self, **kwargs):
        return RetrievalResultSet(results=self.results)


def test_eval_cases_json_loads() -> None:
    cases = EvaluationService().load_eval_cases(EVAL_CASES)

    assert len(cases) >= 5
    assert {case.category for case in cases} >= {"maintenance", "quality", "sop", "material"}
    assert any(not case.should_have_answer for case in cases)


@pytest.mark.asyncio
async def test_evaluation_service_evaluates_single_case(db_session) -> None:
    user = make_user(db_session, "admin", UserRole.admin)
    service = EvaluationService(
        StaticRetrieval(
            [
                chunk(
                    "A200维修手册.txt",
                    "E12 温度传感器异常，需要检查接线并清洁端子。",
                    metadata={"equipment_model": "A200", "fault_code": "E12"},
                )
            ]
        )
    )
    case = EvalCase(
        id="maintenance_001",
        category="maintenance",
        query="A200 设备报 E12 怎么处理？",
        expected_document="A200维修手册",
        expected_keywords=["E12", "温度传感器", "检查接线"],
        expected_metadata={"equipment_model": "A200", "fault_code": "E12"},
    )

    result = await service.evaluate_case(db_session, user, case, [uuid.uuid4()])

    assert result.hit_at_1 is True
    assert result.keyword_match_rate == 1.0
    assert result.metadata_match_rate == 1.0
    assert result.passed is True


def test_hit_at_k_calculation() -> None:
    service = EvaluationService(StaticRetrieval([]))
    case = EvalCase(
        id="material_001",
        category="material",
        query="P-A200-H 的通信协议是什么？",
        expected_document="物料参数表",
    )
    results = [
        chunk("其他资料.txt", "irrelevant"),
        chunk("物料参数表.xlsx", "P-A200-H EtherCAT"),
    ]

    rank = service._hit_rank(case, results)

    assert rank == 2


def test_mrr_calculation() -> None:
    metrics = EvaluationService().calculate_metrics(
        [
            EvalCaseResult(id="a", category="x", query="q", should_have_answer=True, hit_rank=1, hit_at_1=True, hit_at_3=True, hit_at_5=True, reciprocal_rank=1.0),
            EvalCaseResult(id="b", category="x", query="q", should_have_answer=True, hit_rank=3, hit_at_3=True, hit_at_5=True, reciprocal_rank=1 / 3),
        ]
    )

    assert round(metrics.mrr, 4) == 0.6667
    assert metrics.hit_at_1 == 0.5
    assert metrics.hit_at_3 == 1.0


def test_metadata_match_rate_calculation() -> None:
    service = EvaluationService()
    rate = service._metadata_match_rate(
        {"equipment_model": "A200", "fault_code": "E12"},
        [chunk("A200维修手册.txt", "text", metadata={"equipment_model": "A200", "fault_code": "E12"})],
    )

    assert rate == 1.0


@pytest.mark.asyncio
async def test_no_answer_case_does_not_accept_high_confidence_result(db_session) -> None:
    user = make_user(db_session, "admin", UserRole.admin)
    service = EvaluationService(
        StaticRetrieval([chunk("A200维修手册.txt", "unrelated but high score", score=0.91)])
    )
    case = EvalCase(
        id="no_answer_001",
        category="maintenance",
        query="Z900 设备报 F99 如何修复？",
        should_have_answer=False,
    )

    result = await service.evaluate_case(db_session, user, case, [uuid.uuid4()])

    assert result.no_answer_correct is False
    assert result.passed is False


def test_non_admin_cannot_call_evaluation_api(db_session) -> None:
    viewer = make_user(db_session, "viewer", UserRole.viewer)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    try:
        response = TestClient(app).post("/api/evaluation/retrieval/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unready_evaluation_api_returns_clear_error(db_session) -> None:
    admin = make_user(db_session, "api-admin", UserRole.admin)

    with pytest.raises(HTTPException) as exc_info:
        await run_retrieval_evaluation(current_user=admin, db=db_session)

    response_exc = exc_info.value
    assert response_exc.status_code == 400
    detail = response_exc.detail
    assert detail["evaluation_kb_ready"] is False
    assert "missing_documents" in detail
    assert "import_evaluation_fixtures.py" in detail["message"]
