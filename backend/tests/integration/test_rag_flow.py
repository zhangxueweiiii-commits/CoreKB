import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.services.chat_service import ChatService
from app.services.document_ingestion import DocumentIngestionService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.vector_store import VectorStore

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run real PostgreSQL/Qdrant/Redis integration tests.",
)


class FakeEmbeddingService(EmbeddingService):
    async def embed_texts(self, texts):
        return [[0.1] * get_settings().embedding_dimension for _ in texts]


class FakeLLMService(LLMService):
    async def chat(self, messages):
        return "这是基于测试文档的回答。"


@pytest.fixture
def db_session():
    settings = get_settings()
    settings.database_url = os.getenv("INTEGRATION_DATABASE_URL") or settings.database_url
    settings.qdrant_collection = f"corekb_it_rag_{uuid.uuid4().hex}"
    settings.embedding_dimension = int(os.getenv("INTEGRATION_EMBEDDING_DIMENSION", "16"))
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_rag_flow_with_real_postgres_and_qdrant(db_session, tmp_path) -> None:
    settings = get_settings()
    user = User(
        username=f"rag_owner_{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role=UserRole.editor,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    kb = KnowledgeBase(name="RAG IT KB", owner_id=user.id, visibility="private")
    db_session.add(kb)
    db_session.flush()
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=user.id,
            role=KBPermissionRole.owner,
            created_by=user.id,
        )
    )
    path = tmp_path / "policy.txt"
    path.write_text("CoreKB 集成测试文档：报销需要提交发票。", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    vector_store = VectorStore()
    ingestion = DocumentIngestionService()
    ingestion.embedding_service = FakeEmbeddingService()
    ingestion.vector_store = vector_store
    indexed = await ingestion.process(db_session, document)
    assert indexed.status == DocumentStatus.indexed

    retrieval = RetrievalService()
    retrieval.embedding_service = FakeEmbeddingService()
    retrieval.vector_store = vector_store
    results = await retrieval.search(db_session, user, "报销需要什么？", [kb.id], top_k=3)
    assert results
    assert results[0].document_id == document.id

    chat = ChatService()
    chat.retrieval_service = retrieval
    chat.llm_service = FakeLLMService()
    answer, citations, _, _, _, _ = await chat.answer(db_session, user, "报销需要什么？", [kb.id], None)
    assert answer
    assert citations
    assert citations[0]["filename"] == path.name

    await vector_store.client.delete_collection(collection_name=settings.qdrant_collection)
