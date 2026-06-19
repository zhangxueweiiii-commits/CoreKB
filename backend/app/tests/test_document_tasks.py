from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

from app.api.routes.documents import delete_document, retry_indexing, upload_document
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.index_job import IndexJob, IndexJobType
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_parser import ParsedSection


def make_owner_and_kb(db):
    owner = User(username="owner", password_hash="x", role="editor", is_active=True)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    kb = KnowledgeBase(name="kb", owner_id=owner.id, visibility="private")
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
    return owner, kb


class StubParser:
    def parse(self, file_path):
        return [ParsedSection(text="hello world", page_number=1, section_title="Intro")]


class FailingParser:
    def parse(self, file_path):
        raise RuntimeError("parse failed")


class StubEmbedding:
    async def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class StubVectorStore:
    def __init__(self):
        self.deleted: list[str] = []
        self.upserted = []

    async def delete_document(self, document_id: str) -> None:
        self.deleted.append(document_id)

    async def upsert_chunks(self, points):
        self.upserted.extend(points)


class OrderedVectorStore:
    def __init__(self, events):
        self.events = events

    async def delete_document(self, document_id: str) -> None:
        self.events.append(("delete", document_id))

    async def upsert_chunks(self, points):
        self.events.append(("upsert", len(points)))


def make_document(db, kb: KnowledgeBase, path: Path, status=DocumentStatus.uploaded) -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type=path.suffix.lstrip(".") or "txt",
        file_size=path.stat().st_size,
        status=status,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@pytest.mark.asyncio
async def test_upload_document_returns_uploaded_and_enqueues(db_session, tmp_path, monkeypatch) -> None:
    owner, kb = make_owner_and_kb(db_session)
    enqueued = []

    class SettingsStub:
        upload_dir = tmp_path
        max_upload_size_mb = 50

    monkeypatch.setattr("app.api.routes.documents.get_settings", lambda: SettingsStub())
    monkeypatch.setattr("app.api.routes.documents.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))

    file = UploadFile(file=BytesIO(b"hello"), filename="handbook.txt")
    document = await upload_document(kb.id, file, owner, db_session)

    assert document.status == DocumentStatus.uploaded
    job = db_session.query(IndexJob).filter_by(document_id=document.id).one()
    assert job.job_type == IndexJobType.document_index
    assert enqueued == [job.id]


@pytest.mark.asyncio
async def test_process_document_success_sets_indexed(db_session, tmp_path) -> None:
    owner, kb = make_owner_and_kb(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    service = DocumentIngestionService()
    service.parser = StubParser()
    service.embedding_service = StubEmbedding()
    service.vector_store = StubVectorStore()

    result = await service.process(db_session, document)

    assert result.status == DocumentStatus.indexed
    assert result.chunk_count == 1
    assert result.indexed_at is not None


@pytest.mark.asyncio
async def test_process_document_failure_sets_failed(db_session, tmp_path) -> None:
    owner, kb = make_owner_and_kb(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    service = DocumentIngestionService()
    service.parser = FailingParser()
    service.vector_store = StubVectorStore()

    result = await service.process(db_session, document)

    assert result.status == DocumentStatus.failed
    assert "parse failed" in result.error_message


@pytest.mark.asyncio
async def test_retry_indexing_clears_and_enqueues(db_session, tmp_path, monkeypatch) -> None:
    owner, kb = make_owner_and_kb(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path, DocumentStatus.failed)
    enqueued = []

    monkeypatch.setattr("app.api.routes.documents.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))

    result = await retry_indexing(document.id, owner, db_session)

    assert result.job_type == IndexJobType.document_index
    assert result.document_id == document.id
    assert enqueued == [result.id]


@pytest.mark.asyncio
async def test_delete_document_cleans_vectors_and_chunks(db_session, tmp_path, monkeypatch) -> None:
    owner, kb = make_owner_and_kb(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path, DocumentStatus.indexed)
    chunk = DocumentChunk(
        document_id=document.id,
        knowledge_base_id=kb.id,
        chunk_text="hello",
        chunk_index=0,
        meta={},
    )
    db_session.add(chunk)
    db_session.commit()
    deleted = []

    class FakeVectorStore:
        async def delete_document(self, document_id):
            deleted.append(document_id)

    monkeypatch.setattr("app.api.routes.documents.VectorStore", FakeVectorStore)

    await delete_document(document.id, owner, db_session)

    assert deleted == [str(document.id)]
    assert db_session.get(Document, document.id) is None
    assert db_session.query(DocumentChunk).filter_by(document_id=document.id).count() == 0


@pytest.mark.asyncio
async def test_reindex_deletes_old_chunks_and_vectors_before_upsert(db_session, tmp_path) -> None:
    owner, kb = make_owner_and_kb(db_session)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path, DocumentStatus.indexed)
    old_chunk = DocumentChunk(
        document_id=document.id,
        knowledge_base_id=kb.id,
        chunk_text="old",
        chunk_index=0,
        meta={},
    )
    db_session.add(old_chunk)
    db_session.commit()
    events = []
    service = DocumentIngestionService()
    service.parser = StubParser()
    service.embedding_service = StubEmbedding()
    service.vector_store = OrderedVectorStore(events)

    result = await service.process(db_session, document)

    assert result.status == DocumentStatus.indexed
    assert events[0] == ("delete", str(document.id))
    assert events[-1] == ("upsert", 1)
    chunks = db_session.query(DocumentChunk).filter_by(document_id=document.id).all()
    assert len(chunks) == 1
    assert chunks[0].chunk_text == "hello world"
