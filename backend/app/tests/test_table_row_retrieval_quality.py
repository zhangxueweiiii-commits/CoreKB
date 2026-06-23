import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.routes import search as search_routes
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.evaluation_run import EvaluationCaseResult as EvaluationCaseResultRecord
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.schemas.evaluation import EvalCase
from app.schemas.search import SearchRequest
from app.services.chat_service import ChatService
from app.services.evaluation_service import EvaluationService
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet, RetrievalService


TABLE_METADATA = {
    "source_type": "table",
    "sheet_name": "Products",
    "row_start": 4,
    "row_end": 6,
    "column_names": ["material_code", "product_model", "protocol"],
    "table_index": 0,
    "material_code": "P-A200-H",
    "product_model": "A200-H",
    "category": "material",
}


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User, name: str = "Table Retrieval KB") -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description="table retrieval",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def make_document(db, kb: KnowledgeBase, tmp_path: Path, filename: str = "material_parameters.xlsx") -> Document:
    path = tmp_path / filename
    path.write_text("placeholder table source", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=str(path),
        file_type="xlsx",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta={"document_title": "Material parameters", "category": "material"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def make_table_chunk(db, document: Document) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        chunk_text=(
            "File: material_parameters.xlsx\n"
            "Sheet: Products\n"
            "Rows: 4-6\n"
            "Columns: material_code, product_model, protocol\n"
            "Row 4:\nmaterial_code: P-A200-H\nproduct_model: A200-H\nprotocol: EtherCAT"
        ),
        chunk_index=0,
        section_title="Products",
        meta=TABLE_METADATA,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def table_retrieved_chunk(document: Document, chunk: DocumentChunk) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_text=chunk.chunk_text,
        filename=document.filename,
        page_number=None,
        score=0.92,
        document_id=document.id,
        chunk_id=chunk.id,
        section_title="Products",
        metadata=TABLE_METADATA,
        vector_score=0.92,
        final_score=0.92,
    )


@pytest.mark.asyncio
async def test_retrieval_service_preserves_table_row_metadata(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-row-retrieval-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    chunk = make_table_chunk(db_session, document)

    class FakeEmbedding:
        async def embed_query(self, query):
            return [0.1, 0.2]

    class FakeVectorStore:
        async def search(self, vector, kb_ids, top_k, score_threshold, metadata_filter):
            return [
                SimpleNamespace(
                    score=0.92,
                    payload={
                        "chunk_id": str(chunk.id),
                        "document_id": str(document.id),
                        "filename": document.filename,
                        "page_number": None,
                        "section_title": "Products",
                        "sheet_name": "Products",
                        "row_start": 4,
                        "row_end": 6,
                    },
                )
            ]

    service = RetrievalService.__new__(RetrievalService)
    service.settings = SimpleNamespace(default_top_k=5, default_score_threshold=0.0, rerank_top_n=20)
    service.embedding_service = FakeEmbedding()
    service.vector_store = FakeVectorStore()
    service.rerank_service = object()

    result_set = await service.search_with_options(
        db=db_session,
        user=admin,
        query="P-A200-H protocol",
        knowledge_base_ids=[kb.id],
        metadata_filter={"material_code": "P-A200-H"},
    )

    result = result_set.results[0]
    assert result.filename == "material_parameters.xlsx"
    assert result.section_title == "Products"
    assert result.metadata["source_type"] == "table"
    assert result.metadata["sheet_name"] == "Products"
    assert result.metadata["row_start"] == 4
    assert result.metadata["row_end"] == 6


@pytest.mark.asyncio
async def test_search_api_returns_table_row_fields(db_session, tmp_path: Path, monkeypatch) -> None:
    admin = make_user(db_session, "table-row-search-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    chunk = make_table_chunk(db_session, document)

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            assert kwargs["metadata_filter"] == {"material_code": "P-A200-H"}
            return RetrievalResultSet(results=[table_retrieved_chunk(document, chunk)])

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(
            query="P-A200-H protocol",
            knowledge_base_ids=[kb.id],
            metadata_filter={"material_code": "P-A200-H"},
        ),
        admin,
        db_session,
    )

    result = response.results[0]
    assert result.sheet_name == "Products"
    assert result.row_start == 4
    assert result.row_end == 6
    assert result.metadata["column_names"] == ["material_code", "product_model", "protocol"]


def test_chat_citation_uses_table_row_range(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-row-chat-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    chunk = make_table_chunk(db_session, document)

    citation = ChatService.__new__(ChatService).citation(table_retrieved_chunk(document, chunk))

    assert citation["filename"] == "material_parameters.xlsx"
    assert citation["sheet_name"] == "Products"
    assert citation["row_start"] == 4
    assert citation["row_end"] == 6
    assert citation["chunk_id"] == str(chunk.id)
    assert "P-A200-H" in citation["quote"]


@pytest.mark.asyncio
async def test_evaluation_case_top_results_include_table_row_citation(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-row-eval-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    chunk = make_table_chunk(db_session, document)

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(results=[table_retrieved_chunk(document, chunk)])

    case = EvalCase(
        id="material_table_001",
        category="material",
        assistant_type="material",
        query="P-A200-H uses which protocol?",
        expected_document="material_parameters",
        expected_keywords=["P-A200-H", "EtherCAT"],
        expected_metadata={"material_code": "P-A200-H", "product_model": "A200-H"},
        should_have_answer=True,
    )

    result = await EvaluationService(retrieval_service=FakeRetrievalService(), assistant_service=object()).evaluate_case(
        db=db_session,
        user=admin,
        case=case,
        knowledge_base_ids=[kb.id],
        use_metadata_filter=True,
    )

    assert result.passed is True
    top = result.top_results[0]
    assert top["chunk_metadata"]["source_type"] == "table"
    assert top["citation"]["sheet_name"] == "Products"
    assert top["citation"]["row_start"] == 4
    assert top["citation"]["row_end"] == 6


@pytest.mark.asyncio
async def test_persisted_evaluation_case_result_preserves_table_row_snapshot(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-row-eval-persist-admin")
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    document = make_document(db_session, kb, tmp_path)
    chunk = make_table_chunk(db_session, document)
    cases_path = tmp_path / "eval_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "material_table_001",
                    "category": "material",
                    "assistant_type": "material",
                    "query": "P-A200-H uses which protocol?",
                    "expected_document": "material_parameters",
                    "expected_keywords": ["P-A200-H", "EtherCAT"],
                    "expected_metadata": {"material_code": "P-A200-H", "product_model": "A200-H"},
                    "expected_answer_type": "parameter_lookup",
                    "should_have_answer": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(results=[table_retrieved_chunk(document, chunk)])

    response = await EvaluationService(retrieval_service=FakeRetrievalService(), assistant_service=object()).run_retrieval_eval(
        db=db_session,
        user=admin,
        cases_path=cases_path,
        persist=True,
        use_metadata_filter=True,
    )

    record = db_session.query(EvaluationCaseResultRecord).filter_by(case_id="material_table_001").one()
    citation = record.retrieved_results[0]["citation"]
    assert response.case_results[0].case_result_id == record.id
    assert citation["sheet_name"] == "Products"
    assert citation["row_start"] == 4
    assert citation["row_end"] == 6
