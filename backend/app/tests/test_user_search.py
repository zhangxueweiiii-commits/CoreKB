import pytest
from fastapi import HTTPException

from app.api.routes.users import search_users
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole


def add_user(db, username: str, role: UserRole = UserRole.viewer, email: str | None = None, full_name: str | None = None):
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        password_hash="x",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_kb(db, owner: User):
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
    return kb


def test_admin_can_search_all_users(db_session) -> None:
    admin = add_user(db_session, "admin", UserRole.admin)
    add_user(db_session, "alice", email="alice@example.com", full_name="Alice Zhang")

    results = search_users("alice", 20, None, admin, db_session)

    assert len(results) == 1
    assert results[0].name == "Alice Zhang"


def test_kb_owner_can_search_with_kb_context(db_session) -> None:
    owner = add_user(db_session, "owner")
    add_user(db_session, "bob", email="bob@example.com")
    kb = add_kb(db_session, owner)

    results = search_users("bob", 20, kb.id, owner, db_session)

    assert len(results) == 1
    assert results[0].email == "bob@example.com"


def test_viewer_cannot_search_users(db_session) -> None:
    viewer = add_user(db_session, "viewer")

    with pytest.raises(HTTPException) as exc:
        search_users("", 20, None, viewer, db_session)

    assert exc.value.status_code == 403
