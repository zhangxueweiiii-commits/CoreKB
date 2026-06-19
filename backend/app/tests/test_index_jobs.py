import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.index_jobs import get_index_job, index_job_stats, list_index_jobs
from app.api.routes.kb import reindex_knowledge_base
from app.models.document import Document, DocumentStatus
from app.models.index_job import IndexJobItem, IndexJobItemStatus, IndexJobStatus, IndexJobType
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.index_job import ReindexRequest
from app.services.document_parser import ParsedSection
from app.services.index_job_service import IndexJobService
from app.tasks.document_tasks import process_reindex_job


def make_user(db, username: str, role: UserRole = UserRole.viewer) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(name=f"kb-{uuid.uuid4().hex[:6]}", owner_id=owner.id, visibility="private")
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


def make_document(db, kb: KnowledgeBase, path) -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.uploaded,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_reindex_kb_creates_persistent_job(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    enqueued = []
    monkeypatch.setattr("app.api.routes.kb.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))

    job = reindex_knowledge_base(kb.id, ReindexRequest(), owner, db_session)

    assert job.job_type == IndexJobType.kb_reindex
    assert job.total_count == 1
    assert enqueued == [job.id]
    assert job.items[0].document_id == document.id


def test_viewer_cannot_reindex_kb(db_session, tmp_path) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    viewer = make_user(db_session, "viewer")
    kb = make_kb(db_session, owner)
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=viewer.id,
            role=KBPermissionRole.viewer,
            created_by=owner.id,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        reindex_knowledge_base(kb.id, ReindexRequest(), viewer, db_session)

    assert exc.value.status_code == 403


def test_editor_can_reindex_kb(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    editor = make_user(db_session, "editor")
    kb = make_kb(db_session, owner)
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=editor.id,
            role=KBPermissionRole.editor,
            created_by=owner.id,
        )
    )
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    make_document(db_session, kb, path)
    db_session.commit()
    monkeypatch.setattr("app.api.routes.kb.enqueue_reindex_job", lambda job_id: None)

    job = reindex_knowledge_base(kb.id, ReindexRequest(), editor, db_session)

    assert job.job_type == IndexJobType.kb_reindex


def test_user_without_permission_cannot_reindex_kb(db_session, tmp_path) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    outsider = make_user(db_session, "outsider")
    kb = make_kb(db_session, owner)

    with pytest.raises(HTTPException) as exc:
        reindex_knowledge_base(kb.id, ReindexRequest(), outsider, db_session)

    assert exc.value.status_code == 403


class StubParser:
    def parse(self, file_path):
        return [ParsedSection(text="hello world", page_number=1)]


class StubEmbedding:
    async def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class StubVectorStore:
    async def delete_document(self, document_id):
        return None

    async def upsert_chunks(self, points):
        return None


def test_process_reindex_job_updates_counts(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    class FakeIngestion:
        async def process(self, db, document):
            document.status = DocumentStatus.indexed
            document.error_message = None
            document.chunk_count = 1
            db.commit()
            return document

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", FakeIngestion)

    job_id = job.id
    document_id = document.id
    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job_id)
    document = db_session.get(Document, document_id)

    assert job.status == IndexJobStatus.completed
    assert job.success_count == 1
    assert job.failed_count == 0
    assert job.pending_count == 0
    assert document.status == DocumentStatus.indexed


def test_process_reindex_job_partial_failed(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    ok_path = tmp_path / "ok.txt"
    bad_path = tmp_path / "bad.txt"
    ok_path.write_text("ok", encoding="utf-8")
    bad_path.write_text("bad", encoding="utf-8")
    ok_doc = make_document(db_session, kb, ok_path)
    bad_doc = make_document(db_session, kb, bad_path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [ok_doc, bad_doc], owner, True)

    class MixedIngestion:
        async def process(self, db, document):
            if document.id == bad_doc.id:
                document.status = DocumentStatus.failed
                document.error_message = "embedding failed"
            else:
                document.status = DocumentStatus.indexed
                document.error_message = None
            db.commit()
            return document

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", MixedIngestion)

    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)

    assert job.status == IndexJobStatus.partial_failed
    assert job.success_count == 1
    assert job.failed_count == 1


def test_process_reindex_job_all_failed(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first", encoding="utf-8")
    second_path.write_text("second", encoding="utf-8")
    docs = [make_document(db_session, kb, first_path), make_document(db_session, kb, second_path)]
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, docs, owner, True)

    class FailingIngestion:
        async def process(self, db, document):
            document.status = DocumentStatus.failed
            document.error_message = "parse failed"
            db.commit()
            return document

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", FailingIngestion)

    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)

    assert job.status == IndexJobStatus.failed
    assert job.success_count == 0
    assert job.failed_count == 2


def test_index_job_stats_include_failed_jobs(db_session, tmp_path) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    job.status = IndexJobStatus.failed
    job.failed_count = 1
    job.pending_count = 0
    db_session.commit()

    stats = index_job_stats(owner, db_session)
    jobs = list_index_jobs(None, None, kb.id, 50, 0, owner, db_session)

    assert stats.failed_count == 1
    assert stats.failed_recent_count == 1
    assert jobs[0].id == job.id


def test_index_jobs_do_not_return_unauthorized_kb_jobs(db_session, tmp_path) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    outsider = make_user(db_session, "outsider")
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    jobs = list_index_jobs(None, None, None, 50, 0, outsider, db_session)

    assert jobs == []


def test_index_job_detail_does_not_leak_unauthorized_documents(db_session, tmp_path) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    outsider = make_user(db_session, "outsider")
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    with pytest.raises(HTTPException) as exc:
        get_index_job(job.id, outsider, db_session)

    assert exc.value.status_code == 403


def test_retry_failed_creates_new_job(db_session, tmp_path, monkeypatch) -> None:
    from app.api.routes.index_jobs import retry_failed_items

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    source_job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    item = db_session.query(IndexJobItem).filter_by(job_id=source_job.id).one()
    item.status = IndexJobItemStatus.failed
    item.error_message = "embedding failed"
    source_job.status = IndexJobStatus.failed
    source_job.failed_count = 1
    source_job.pending_count = 0
    db_session.commit()
    enqueued = []
    monkeypatch.setattr("app.api.routes.index_jobs.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))

    response = retry_failed_items(source_job.id, owner, db_session)

    assert response.job is not None
    assert response.job.job_type == IndexJobType.retry_failed
    assert response.job.total_count == 1
    assert enqueued == [response.job.id]
    assert response.job.id != source_job.id


def test_retry_failed_without_failed_items_returns_message(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import retry_failed_items

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    response = retry_failed_items(job.id, owner, db_session)

    assert response.job is None
    assert "No failed items" in response.message


def test_cancel_pending_job_marks_pending_items_cancelled(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import cancel_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    response = cancel_index_job(job.id, owner, db_session)
    item = db_session.query(IndexJobItem).filter_by(job_id=job.id).one()

    assert response.job.status == IndexJobStatus.cancelled
    assert item.status == IndexJobItemStatus.cancelled


def test_viewer_cannot_cancel_index_job(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import cancel_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    viewer = make_user(db_session, "viewer")
    kb = make_kb(db_session, owner)
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=viewer.id,
            role=KBPermissionRole.viewer,
            created_by=owner.id,
        )
    )
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    with pytest.raises(HTTPException) as exc:
        cancel_index_job(job.id, viewer, db_session)

    assert exc.value.status_code == 403


def test_pause_and_resume_index_job(db_session, tmp_path, monkeypatch) -> None:
    from app.api.routes.index_jobs import pause_index_job, resume_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    enqueued = []
    monkeypatch.setattr("app.api.routes.index_jobs.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))

    paused = pause_index_job(job.id, owner, db_session)
    resumed = resume_index_job(job.id, owner, db_session)

    assert paused.job.status == IndexJobStatus.paused
    assert resumed.job.status == IndexJobStatus.pending
    assert enqueued == [job.id]


def test_viewer_cannot_pause_index_job(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import pause_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    viewer = make_user(db_session, "viewer")
    kb = make_kb(db_session, owner)
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=viewer.id,
            role=KBPermissionRole.viewer,
            created_by=owner.id,
        )
    )
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)

    with pytest.raises(HTTPException) as exc:
        pause_index_job(job.id, viewer, db_session)

    assert exc.value.status_code == 403


def test_completed_job_cannot_be_paused(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import pause_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    job.status = IndexJobStatus.completed
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        pause_index_job(job.id, owner, db_session)

    assert exc.value.status_code == 400


def test_viewer_cannot_resume_index_job(db_session, tmp_path) -> None:
    from app.api.routes.index_jobs import resume_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    viewer = make_user(db_session, "viewer")
    kb = make_kb(db_session, owner)
    db_session.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=viewer.id,
            role=KBPermissionRole.viewer,
            created_by=owner.id,
        )
    )
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    job.status = IndexJobStatus.paused
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        resume_index_job(job.id, viewer, db_session)

    assert exc.value.status_code == 403


def test_worker_stops_when_job_paused_before_pending_items(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first", encoding="utf-8")
    second_path.write_text("second", encoding="utf-8")
    first = make_document(db_session, kb, first_path)
    second = make_document(db_session, kb, second_path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [first, second], owner, True)
    processed = []

    class PausingIngestion:
        async def process(self, db, document):
            processed.append(document.id)
            document.status = DocumentStatus.indexed
            document.error_message = None
            if len(processed) == 1:
                current_job = db.get(type(job), job.id)
                current_job.status = IndexJobStatus.paused
            db.commit()
            return document

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", PausingIngestion)

    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)
    items = db_session.query(IndexJobItem).filter_by(job_id=job.id).order_by(IndexJobItem.created_at.asc()).all()

    assert processed == [first.id]
    assert job.status == IndexJobStatus.paused
    assert items[0].status == IndexJobItemStatus.completed
    assert items[1].status == IndexJobItemStatus.pending


def test_resume_continues_pending_items(db_session, tmp_path, monkeypatch) -> None:
    from app.api.routes.index_jobs import resume_index_job

    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first", encoding="utf-8")
    second_path.write_text("second", encoding="utf-8")
    first = make_document(db_session, kb, first_path)
    second = make_document(db_session, kb, second_path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [first, second], owner, True)
    items = db_session.query(IndexJobItem).filter_by(job_id=job.id).order_by(IndexJobItem.created_at.asc()).all()
    items[0].status = IndexJobItemStatus.completed
    job.status = IndexJobStatus.paused
    db_session.commit()
    enqueued = []
    processed = []

    class PendingOnlyIngestion:
        async def process(self, db, document):
            processed.append(document.id)
            document.status = DocumentStatus.indexed
            document.error_message = None
            db.commit()
            return document

    monkeypatch.setattr("app.api.routes.index_jobs.enqueue_reindex_job", lambda job_id: enqueued.append(job_id))
    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", PendingOnlyIngestion)

    response = resume_index_job(job.id, owner, db_session)
    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)
    items = db_session.query(IndexJobItem).filter_by(job_id=job.id).order_by(IndexJobItem.created_at.asc()).all()

    assert response.job.status == IndexJobStatus.pending
    assert enqueued == [job.id]
    assert processed == [second.id]
    assert job.status == IndexJobStatus.completed
    assert all(item.status == IndexJobItemStatus.completed for item in items)


def test_worker_stops_when_job_cancelled(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    job.status = IndexJobStatus.cancelled
    db_session.commit()

    class ShouldNotRunIngestion:
        async def process(self, db, document):
            raise AssertionError("cancelled job should not process documents")

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", ShouldNotRunIngestion)

    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)

    assert job.status == IndexJobStatus.cancelled
