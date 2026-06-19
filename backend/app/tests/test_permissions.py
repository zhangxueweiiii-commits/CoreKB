import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.chat import chat
from app.api.routes.kb import create_permission, delete_permission
from app.api.routes.search import search
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.chat import ChatRequest
from app.schemas.kb import KBPermissionCreate
from app.schemas.search import SearchRequest
from app.services.permission_service import PermissionService


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


def test_admin_can_access_all_knowledge_bases(db_session) -> None:
    owner = make_user(db_session, "owner")
    admin = make_user(db_session, "admin", UserRole.admin)
    kb = make_kb(db_session, owner)

    assert PermissionService(db_session).can_manage_kb(admin, kb.id)


def test_owner_can_grant_user_permission(db_session) -> None:
    owner = make_user(db_session, "owner")
    viewer = make_user(db_session, "viewer")
    kb = make_kb(db_session, owner)

    permission = create_permission(
        kb.id,
        KBPermissionCreate(user_id=viewer.id, role=KBPermissionRole.viewer),
        owner,
        db_session,
    )

    assert permission.user_id == viewer.id
    assert permission.role == KBPermissionRole.viewer


def test_viewer_cannot_upload_documents(db_session) -> None:
    owner = make_user(db_session, "owner")
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

    assert not PermissionService(db_session).can_edit_kb(viewer, kb.id)


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_search_kb(db_session) -> None:
    owner = make_user(db_session, "owner")
    other = make_user(db_session, "other")
    kb = make_kb(db_session, owner)

    with pytest.raises(HTTPException) as exc:
        await search(
            SearchRequest(query="policy", knowledge_base_ids=[kb.id]),
            other,
            db_session,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_chat_filters_out_unauthorized_kbs(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner")
    viewer = make_user(db_session, "viewer")
    allowed = make_kb(db_session, owner, "allowed")
    blocked = make_kb(db_session, owner, "blocked")
    db_session.add(
        KBPermission(
            knowledge_base_id=allowed.id,
            user_id=viewer.id,
            role=KBPermissionRole.viewer,
            created_by=owner.id,
        )
    )
    db_session.commit()
    seen_ids: list[uuid.UUID] = []

    class FakeChatService:
        async def answer(self, db, user, message, knowledge_base_ids, conversation_id, **kwargs):
            seen_ids.extend(knowledge_base_ids)
            return "answer", [], type("ConversationStub", (), {"id": uuid.uuid4()})(), {}, False, None

    monkeypatch.setattr("app.api.routes.chat.ChatService", FakeChatService)

    await chat(
        ChatRequest(message="hello", knowledge_base_ids=[allowed.id, blocked.id]),
        viewer,
        db_session,
    )

    assert seen_ids == [allowed.id]


def test_cannot_delete_last_owner(db_session) -> None:
    owner = make_user(db_session, "owner")
    kb = make_kb(db_session, owner)
    permission = db_session.query(KBPermission).filter_by(knowledge_base_id=kb.id).one()

    with pytest.raises(HTTPException) as exc:
        delete_permission(kb.id, permission.id, owner, db_session)

    assert exc.value.status_code == 400
