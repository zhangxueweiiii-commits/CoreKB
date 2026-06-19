import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.routes import chat as chat_routes
from app.api.routes import search as search_routes
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.evaluation_run import EvaluationRun
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.chat import ChatRequest
from app.schemas.search import SearchRequest
from app.services.evaluation_service import EvaluationService
from app.services.query_metadata_extractor import extract_metadata_from_query, sanitize_metadata_filter
from app.services.rerank_service import RerankService
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet, RetrievalService
from app.services.vector_store import build_qdrant_metadata_filter


def make_user(db, username: str, role: UserRole = UserRole.viewer) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User, name: str = "kb") -> KnowledgeBase:
    kb = KnowledgeBase(name=name, owner_id=owner.id, visibility="private")
    db.add(kb)
    db.flush()
    db.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=owner.id,
            role=KBPermissionRole.owner,
            created_by=owner.id,
        )
    )
    db.commit()
    db.refresh(kb)
    return kb


def test_query_metadata_extractor_recognizes_equipment_model() -> None:
    assert extract_metadata_from_query("A200 设备异常")["equipment_model"] == "A200"
    assert extract_metadata_from_query("A-200 设备异常")["equipment_model"] == "A200"
    assert extract_metadata_from_query("EQ-A200 设备异常")["equipment_model"] == "EQ-A200"


@pytest.mark.parametrize("query", ["E12 怎么处理", "E-12 怎么处理", "ERR12 怎么处理", "Error 12 怎么处理", "故障码 E12"])
def test_query_metadata_extractor_recognizes_fault_codes(query: str) -> None:
    assert extract_metadata_from_query(query)["fault_code"] == "E12"


def test_query_metadata_extractor_recognizes_material_code() -> None:
    assert extract_metadata_from_query("MAT-001 可以替代吗")["material_code"] == "MAT-001"
    assert extract_metadata_from_query("物料 MAT-001 可以替代吗")["material_code"] == "MAT-001"


def test_query_metadata_extractor_recognizes_sop_code() -> None:
    assert extract_metadata_from_query("作业指导书 SOP-001")["sop_code"] == "SOP-001"
    assert extract_metadata_from_query("SOP001 怎么操作")["sop_code"] == "SOP001"


def test_query_metadata_extractor_does_not_match_plain_numbers() -> None:
    metadata = extract_metadata_from_query("2024 年第 12 页有 200 个样本")

    assert "equipment_model" not in metadata
    assert "fault_code" not in metadata
    assert "material_code" not in metadata


def test_non_whitelisted_metadata_fields_are_ignored() -> None:
    sanitized = sanitize_metadata_filter({"equipment_model": "A200", "tenant_id": "secret", "empty": ""})

    assert sanitized == {"equipment_model": "A200"}


def test_build_qdrant_metadata_filter_constructs_and_conditions() -> None:
    conditions = build_qdrant_metadata_filter({"equipment_model": "A200", "fault_code": "E12"})

    assert len(conditions) == 2
    assert {condition.key for condition in conditions} == {"equipment_model", "fault_code"}


@pytest.mark.asyncio
async def test_rerank_service_sorts_by_rerank_score(monkeypatch) -> None:
    chunks = [
        RetrievedChunk("low", "a.txt", None, 0.9, uuid.uuid4(), uuid.uuid4(), vector_score=0.9, final_score=0.9),
        RetrievedChunk("high", "b.txt", None, 0.6, uuid.uuid4(), uuid.uuid4(), vector_score=0.6, final_score=0.6),
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"index": 0, "relevance_score": 0.1}, {"index": 1, "relevance_score": 0.95}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    service = RerankService()
    service.settings = SimpleNamespace(
        rerank_enabled=True,
        rerank_base_url="http://rerank.local",
        rerank_model="rerank-test",
        rerank_api_key=None,
        llm_timeout_seconds=5,
    )
    monkeypatch.setattr("app.services.rerank_service.httpx.AsyncClient", FakeClient)

    reranked = await service.rerank_results("query", chunks, top_n=2)

    assert reranked[0].chunk_text == "high"
    assert reranked[0].rerank_score == 0.95
    assert reranked[0].final_score == 0.95


@pytest.mark.asyncio
async def test_search_api_passes_metadata_filter_and_returns_metadata(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    seen_filter = {}

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            seen_filter.update(kwargs["metadata_filter"])
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="E12 温度传感器异常",
                        filename="A200维修手册.txt",
                        page_number=None,
                        score=0.91,
                        document_id=uuid.uuid4(),
                        chunk_id=uuid.uuid4(),
                        metadata={"equipment_model": "A200", "fault_code": "E12"},
                        vector_score=0.91,
                        final_score=0.91,
                    )
                ]
            )

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(
            query="A200 E12",
            knowledge_base_ids=[kb.id],
            metadata_filter={"equipment_model": "A200", "ignored": "x"},
        ),
        owner,
        db_session,
    )

    assert seen_filter == {"equipment_model": "A200"}
    assert response.results[0].metadata["fault_code"] == "E12"


@pytest.mark.asyncio
async def test_search_api_use_rerank_returns_rerank_applied(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner-rerank", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-rerank")

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            assert kwargs["use_rerank"] is True
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="reranked",
                        filename="guide.txt",
                        page_number=None,
                        score=0.5,
                        document_id=uuid.uuid4(),
                        chunk_id=uuid.uuid4(),
                        vector_score=0.5,
                        rerank_score=0.99,
                        final_score=0.99,
                    )
                ],
                use_rerank=True,
                rerank_applied=True,
            )

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(query="hello", knowledge_base_ids=[kb.id], use_rerank=True),
        owner,
        db_session,
    )

    assert response.rerank_applied is True
    assert response.results[0].rerank_score == 0.99


@pytest.mark.asyncio
async def test_search_api_fallbacks_when_rerank_fails(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner-fallback", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-fallback")

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="vector result",
                        filename="guide.txt",
                        page_number=None,
                        score=0.8,
                        document_id=uuid.uuid4(),
                        chunk_id=uuid.uuid4(),
                        vector_score=0.8,
                        final_score=0.8,
                    )
                ],
                use_rerank=True,
                rerank_applied=False,
                rerank_error="Rerank is disabled by RERANK_ENABLED=false",
            )

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(query="hello", knowledge_base_ids=[kb.id], use_rerank=True),
        owner,
        db_session,
    )

    assert response.rerank_applied is False
    assert "RERANK_ENABLED=false" in response.rerank_error
    assert response.results[0].final_score == 0.8


@pytest.mark.asyncio
async def test_metadata_filter_no_match_returns_empty_results(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner-empty", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-empty")

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(results=[])

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(
            query="A200 E12",
            knowledge_base_ids=[kb.id],
            metadata_filter={"equipment_model": "NOPE"},
        ),
        owner,
        db_session,
    )

    assert response.results == []


@pytest.mark.asyncio
async def test_metadata_filter_no_results_does_not_call_rerank(db_session) -> None:
    owner = make_user(db_session, "owner-no-hit", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-no-hit")

    class FakeEmbedding:
        async def embed_query(self, query):
            return [0.1, 0.2]

    class FakeVectorStore:
        seen_filter = None

        async def search(self, vector, kb_ids, top_k, score_threshold, metadata_filter):
            self.seen_filter = metadata_filter
            return []

    class FailingRerank:
        async def rerank_results(self, *args, **kwargs):
            raise AssertionError("rerank should not be called when vector results are empty")

    service = RetrievalService()
    vector_store = FakeVectorStore()
    service.embedding_service = FakeEmbedding()
    service.vector_store = vector_store
    service.rerank_service = FailingRerank()

    result = await service.search_with_options(
        db=db_session,
        user=owner,
        query="A200 E12",
        knowledge_base_ids=[kb.id],
        metadata_filter={"equipment_model": "A200"},
        use_rerank=True,
    )

    assert result.results == []
    assert result.rerank_applied is False
    assert vector_store.seen_filter == {"equipment_model": "A200"}


@pytest.mark.asyncio
async def test_metadata_filter_then_rerank_order(db_session) -> None:
    owner = make_user(db_session, "owner-order", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-order")
    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()
    db_session.add(
        DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            knowledge_base_id=kb.id,
            chunk_text="A200 E12 handling",
            chunk_index=0,
            meta={"equipment_model": "A200", "fault_code": "E12"},
        )
    )
    db_session.commit()

    class FakeEmbedding:
        async def embed_query(self, query):
            return [0.1, 0.2]

    class FakeVectorStore:
        async def search(self, vector, kb_ids, top_k, score_threshold, metadata_filter):
            assert metadata_filter == {"equipment_model": "A200"}
            return [
                SimpleNamespace(
                    score=0.7,
                    payload={
                        "chunk_id": str(chunk_id),
                        "document_id": str(document_id),
                        "filename": "A200维修手册.txt",
                        "page_number": None,
                    },
                )
            ]

    class FakeRerank:
        async def rerank_results(self, query, results, top_n):
            assert results[0].metadata["equipment_model"] == "A200"
            return [
                RetrievedChunk(
                    **{**results[0].__dict__, "rerank_score": 0.99, "final_score": 0.99}
                )
            ]

    service = RetrievalService()
    service.embedding_service = FakeEmbedding()
    service.vector_store = FakeVectorStore()
    service.rerank_service = FakeRerank()

    result = await service.search_with_options(
        db=db_session,
        user=owner,
        query="A200 E12",
        knowledge_base_ids=[kb.id],
        metadata_filter={"equipment_model": "A200"},
        use_rerank=True,
    )

    assert result.rerank_applied is True
    assert result.results[0].final_score == 0.99


@pytest.mark.asyncio
async def test_rerank_disabled_returns_explicit_error(db_session) -> None:
    owner = make_user(db_session, "owner-disabled", UserRole.editor)
    kb = make_kb(db_session, owner, "kb-disabled")
    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()
    db_session.add(
        DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            knowledge_base_id=kb.id,
            chunk_text="A200 E12 handling",
            chunk_index=0,
            meta={"equipment_model": "A200"},
        )
    )
    db_session.commit()

    class FakeEmbedding:
        async def embed_query(self, query):
            return [0.1, 0.2]

    class FakeVectorStore:
        async def search(self, vector, kb_ids, top_k, score_threshold, metadata_filter):
            return [
                SimpleNamespace(
                    score=0.7,
                    payload={
                        "chunk_id": str(chunk_id),
                        "document_id": str(document_id),
                        "filename": "A200维修手册.txt",
                    },
                )
            ]

    service = RetrievalService()
    service.embedding_service = FakeEmbedding()
    service.vector_store = FakeVectorStore()

    result = await service.search_with_options(
        db=db_session,
        user=owner,
        query="A200 E12",
        knowledge_base_ids=[kb.id],
        use_rerank=True,
    )

    assert result.rerank_applied is False
    assert "RERANK_ENABLED=false" in result.rerank_error
    assert result.results[0].final_score == result.results[0].vector_score


@pytest.mark.asyncio
async def test_chat_auto_metadata_filter_returns_used_filter(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "chat-owner", UserRole.editor)
    kb = make_kb(db_session, owner, "chat-kb")

    class FakeChatService:
        async def answer(
            self,
            db,
            user,
            message,
            knowledge_base_ids,
                conversation_id,
                metadata_filter=None,
                auto_metadata_filter=False,
                use_rerank=False,
                rerank_top_n=None,
            ):
            used_filter = {"equipment_model": "A200", "fault_code": "E12"} if auto_metadata_filter else {}
            return "当前知识库未找到可靠依据。", [], type("ConversationStub", (), {"id": uuid.uuid4()})(), used_filter, auto_metadata_filter, None

    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    response = await chat_routes.chat(
        ChatRequest(message="A200 设备报 E12", knowledge_base_ids=[kb.id], auto_metadata_filter=True),
        owner,
        db_session,
    )

    assert response.used_metadata_filter == {"equipment_model": "A200", "fault_code": "E12"}


@pytest.mark.asyncio
async def test_chat_use_rerank_returns_rerank_applied(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "chat-rerank-owner", UserRole.editor)
    kb = make_kb(db_session, owner, "chat-rerank-kb")

    class FakeChatService:
        async def answer(self, **kwargs):
            assert kwargs["use_rerank"] is True
            return "answer", [], type("ConversationStub", (), {"id": uuid.uuid4()})(), {}, True, None

    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    response = await chat_routes.chat(
        ChatRequest(message="hello", knowledge_base_ids=[kb.id], use_rerank=True),
        owner,
        db_session,
    )

    assert response.use_rerank is True
    assert response.rerank_applied is True


@pytest.mark.asyncio
async def test_evaluation_use_metadata_filter_records_metric_config(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    document = Document(
        knowledge_base_id=kb.id,
        filename="maintenance_A200.txt",
        file_path=str(tmp_path / "maintenance_A200.txt"),
        file_type="txt",
        file_size=1,
        status=DocumentStatus.indexed,
        meta={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
    )
    db_session.add(document)
    db_session.commit()
    case_path = tmp_path / "eval_cases.json"
    case_path.write_text(
        json.dumps(
            [
                {
                    "id": "maintenance_001",
                    "category": "maintenance",
                    "query": "A200 设备报 E12 怎么处理？",
                    "expected_document": "A200维修手册",
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200", "fault_code": "E12"},
                    "should_have_answer": True,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class StaticRetrieval:
        async def search_with_options(self, **kwargs):
            assert kwargs["metadata_filter"] == {"equipment_model": "A200", "fault_code": "E12"}
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="E12 温度传感器异常",
                        filename="maintenance_A200.txt",
                        page_number=None,
                        score=0.9,
                        document_id=document.id,
                        chunk_id=uuid.uuid4(),
                        metadata={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
                        vector_score=0.9,
                        final_score=0.9,
                    )
                ]
            )

    result = await EvaluationService(StaticRetrieval()).run_retrieval_eval(
        db=db_session,
        user=admin,
        cases_path=case_path,
        use_metadata_filter=True,
    )

    run = db_session.query(EvaluationRun).one()
    assert result.use_metadata_filter is True
    assert run.metrics["use_metadata_filter"] is True
    assert result.failed_cases == []


@pytest.mark.asyncio
async def test_evaluation_run_supports_use_rerank(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-rerank-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    document = Document(
        knowledge_base_id=kb.id,
        filename="maintenance_A200.txt",
        file_path=str(tmp_path / "maintenance_A200.txt"),
        file_type="txt",
        file_size=1,
        status=DocumentStatus.indexed,
        meta={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
    )
    db_session.add(document)
    db_session.commit()
    case_path = tmp_path / "eval_cases.json"
    case_path.write_text(
        json.dumps(
            [
                {
                    "id": "maintenance_001",
                    "category": "maintenance",
                    "query": "A200 设备报 E12 怎么处理？",
                    "expected_document": "A200维修手册",
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200", "fault_code": "E12"},
                    "should_have_answer": True,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class StaticRetrieval:
        async def search_with_options(self, **kwargs):
            assert kwargs["use_rerank"] is True
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="E12 温度传感器异常",
                        filename="maintenance_A200.txt",
                        page_number=None,
                        score=0.9,
                        document_id=document.id,
                        chunk_id=uuid.uuid4(),
                        metadata={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
                        vector_score=0.9,
                        rerank_score=0.95,
                        final_score=0.95,
                    )
                ],
                use_rerank=True,
                rerank_applied=True,
            )

    result = await EvaluationService(StaticRetrieval()).run_retrieval_eval(
        db=db_session,
        user=admin,
        cases_path=case_path,
        use_metadata_filter=True,
        use_rerank=True,
        rerank_top_n=10,
    )

    run = db_session.query(EvaluationRun).one()
    assert result.use_rerank is True
    assert result.rerank_top_n == 10
    assert run.metrics["use_rerank"] is True
    assert run.metrics["rerank_top_n"] == 10


@pytest.mark.asyncio
async def test_evaluation_compare_returns_three_metric_sets_and_delta(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-compare-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    document = Document(
        knowledge_base_id=kb.id,
        filename="maintenance_A200.txt",
        file_path=str(tmp_path / "maintenance_A200.txt"),
        file_type="txt",
        file_size=1,
        status=DocumentStatus.indexed,
        meta={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
    )
    db_session.add(document)
    db_session.commit()
    case_path = tmp_path / "eval_cases.json"
    case_path.write_text(
        json.dumps(
            [
                {
                    "id": "maintenance_001",
                    "category": "maintenance",
                    "query": "A200 设备报 E12 怎么处理？",
                    "expected_document": "A200维修手册",
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200", "fault_code": "E12"},
                    "should_have_answer": True,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class StaticRetrieval:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="E12 温度传感器异常",
                        filename="maintenance_A200.txt",
                        page_number=None,
                        score=0.9,
                        document_id=document.id,
                        chunk_id=uuid.uuid4(),
                        metadata={"document_title": "A200维修手册", "equipment_model": "A200", "fault_code": "E12"},
                        vector_score=0.9,
                        rerank_score=0.95 if kwargs["use_rerank"] else None,
                        final_score=0.95 if kwargs["use_rerank"] else 0.9,
                    )
                ],
                use_rerank=kwargs["use_rerank"],
                rerank_applied=kwargs["use_rerank"],
            )

    service = EvaluationService(StaticRetrieval())
    original_loader = service.load_eval_cases
    service.load_eval_cases = lambda path=None: original_loader(case_path)

    result = await service.compare_retrieval_eval(db=db_session, user=admin)

    assert result.baseline.mode == "baseline"
    assert result.metadata_filter.mode == "metadata_filter"
    assert result.metadata_filter_rerank.mode == "metadata_filter_rerank"
    assert "metadata_filter_rerank_vs_baseline" in result.delta
    assert "hit_at_1" in result.delta["metadata_filter_rerank_vs_baseline"]
