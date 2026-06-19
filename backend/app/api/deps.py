from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.request_context import set_request_user_id
from app.db.session import get_db
from app.models.knowledge_base import KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.services.permission_service import PermissionService


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    set_request_user_id(str(user.id))
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def get_kb_or_404(db: Session, kb_id: UUID) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


def assert_can_view_kb(db: Session, user: User, kb: KnowledgeBase) -> None:
    PermissionService(db).require_kb_permission(user, kb.id, KBPermissionRole.viewer)


def assert_can_edit_kb(db: Session, user: User, kb: KnowledgeBase) -> None:
    PermissionService(db).require_kb_permission(user, kb.id, KBPermissionRole.editor)


def assert_can_manage_kb(db: Session, user: User, kb: KnowledgeBase) -> None:
    if not PermissionService(db).can_manage_kb(user, kb.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No manage access")
