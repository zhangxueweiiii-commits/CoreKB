import uuid
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi import UploadFile
from sqlalchemy import select

from app.api.routes import auth as auth_routes
from app.api.routes.audit_logs import list_audit_logs
from app.api.routes import chat as chat_routes
from app.api.routes import documents as document_routes
from app.api.routes import kb as kb_routes
from app.api.routes import search as search_routes
from app.core.request_context import RequestContext, set_request_context
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest
from app.schemas.chat import ChatRequest
from app.schemas.kb import KnowledgeBaseCreate
from app.schemas.search import SearchRequest
from app.services.audit_service import AuditService
from app.services.retrieval_service import RetrievalResultSet


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


def test_audit_service_redacts_sensitive_metadata(db_session) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)

    log = AuditService(db_session).record(
        actor=admin,
        action="user.create",
        resource_type="user",
        resource_id=admin.id,
        metadata={"password": "secret", "api_key": "sk-test", "note": "ok"},
    )

    assert log.meta["password"] == "[redacted]"
    assert log.meta["api_key"] == "[redacted]"
    assert log.meta["note"] == "ok"


def test_audit_service_recursively_redacts_and_truncates_metadata(db_session) -> None:
    admin = make_user(db_session, "admin-recursive", UserRole.admin)
    long_note = "x" * 600

    log = AuditService(db_session).record(
        actor=admin,
        action="audit.test",
        resource_type="audit",
        resource_id=admin.id,
        metadata={
            "nested": {
                "token": "secret-token",
                "note": long_note,
                "items": [{"api_key": "sk-test", "safe": "ok"}],
            },
            "content": "full source document text",
        },
    )

    assert log.meta["content"] == "[redacted]"
    assert log.meta["nested"]["token"] == "[redacted]"
    assert log.meta["nested"]["items"][0]["api_key"] == "[redacted]"
    assert log.meta["nested"]["items"][0]["safe"] == "ok"
    assert len(log.meta["nested"]["note"]) == 500


def test_audit_service_records_request_context_without_sensitive_metadata(db_session) -> None:
    admin = make_user(db_session, "admin-context", UserRole.admin)
    set_request_context(
        RequestContext(
            request_id="audit-request-123",
            ip_address="127.0.0.1",
            user_agent="pytest-agent",
        )
    )

    try:
        log = AuditService(db_session).record(
            actor=admin,
            action="audit.context",
            resource_type="audit",
            metadata={"password": "secret"},
        )
    finally:
        set_request_context(RequestContext())

    assert log.request_id == "audit-request-123"
    assert log.ip_address == "127.0.0.1"
    assert log.user_agent == "pytest-agent"
    assert log.meta["password"] == "[redacted]"


def test_successful_login_writes_audit_log(db_session) -> None:
    user = User(username="alice", password_hash=get_password_hash("secret"), role=UserRole.viewer, is_active=True)
    db_session.add(user)
    db_session.commit()

    response = auth_routes.login(LoginRequest(username="alice", password="secret"), db_session)

    log = db_session.scalar(select(AuditLog).where(AuditLog.action == "user.login"))
    assert response.access_token
    assert log is not None
    assert log.status == "success"
    assert log.actor_user_id == user.id


def test_create_kb_writes_audit_log(db_session) -> None:
    editor = make_user(db_session, "editor", UserRole.editor)

    kb = kb_routes.create_knowledge_base(KnowledgeBaseCreate(name="Ops KB"), editor, db_session)

    log = db_session.scalar(select(AuditLog).where(AuditLog.action == "kb.create"))
    assert kb.name == "Ops KB"
    assert log is not None
    assert log.knowledge_base_id == kb.id


@pytest.mark.asyncio
async def test_upload_document_writes_audit_log(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    monkeypatch.setattr(
        document_routes,
        "get_settings",
        lambda: SimpleNamespace(upload_dir=tmp_path / "uploads", max_upload_size_mb=5),
    )
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)
    upload = UploadFile(filename="guide.txt", file=BytesIO(b"hello"))

    document = await document_routes.upload_document(kb.id, upload, owner, db_session)

    log = db_session.scalar(select(AuditLog).where(AuditLog.action == "document.upload"))
    assert document.filename == "guide.txt"
    assert log is not None
    assert log.document_id == document.id
    assert log.meta["filename"] == "guide.txt"


@pytest.mark.asyncio
async def test_chat_and_search_write_audit_logs(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)

    class EmptyRetrievalService:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(results=[])

    class FakeChatService:
        async def answer(self, db, user, message, knowledge_base_ids, conversation_id, **kwargs):
            conversation = Conversation(
                user_id=user.id,
                title=message,
                knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids],
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return "当前知识库未找到可靠依据。", [], conversation, {}, False, None

    monkeypatch.setattr(search_routes, "RetrievalService", EmptyRetrievalService)
    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    await search_routes.search(SearchRequest(query="hello", knowledge_base_ids=[kb.id]), owner, db_session)
    await chat_routes.chat(ChatRequest(message="hello", knowledge_base_ids=[kb.id]), owner, db_session)

    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "search.query" in actions
    assert "chat.ask" in actions


def test_admin_can_list_audit_logs(db_session) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)
    AuditService(db_session).record(
        actor=admin,
        action="kb.create",
        resource_type="knowledge_base",
        resource_id=uuid.uuid4(),
    )

    rows = list_audit_logs(None, None, None, None, None, None, 50, 0, admin, db_session)

    assert len(rows) == 1
    assert rows[0].action == "kb.create"


def test_owner_can_only_list_own_kb_audit_logs(db_session) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    other = make_user(db_session, "other", UserRole.editor)
    kb = make_kb(db_session, owner)
    other_kb = make_kb(db_session, other)
    AuditService(db_session).record(
        actor=owner,
        action="document.upload",
        resource_type="document",
        knowledge_base_id=kb.id,
    )
    AuditService(db_session).record(
        actor=other,
        action="document.upload",
        resource_type="document",
        knowledge_base_id=other_kb.id,
    )

    rows = list_audit_logs(None, None, None, None, None, None, 50, 0, owner, db_session)

    assert len(rows) == 1
    assert rows[0].knowledge_base_id == kb.id


def test_viewer_cannot_list_audit_logs(db_session) -> None:
    viewer = make_user(db_session, "viewer")

    with pytest.raises(HTTPException) as exc:
        list_audit_logs(None, None, None, None, None, None, 50, 0, viewer, db_session)

    assert exc.value.status_code == 403
