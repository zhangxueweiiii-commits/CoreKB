from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole


ROLE_RANK = {
    KBPermissionRole.viewer: 1,
    KBPermissionRole.editor: 2,
    KBPermissionRole.owner: 3,
}


class PermissionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def role_for_kb(self, user: User, kb_id: UUID) -> KBPermissionRole | None:
        if user.role == UserRole.admin:
            return KBPermissionRole.owner
        kb = self.db.get(KnowledgeBase, kb_id)
        if not kb:
            return None
        if kb.owner_id == user.id:
            return KBPermissionRole.owner
        permission = self.db.scalar(
            select(KBPermission).where(
                KBPermission.knowledge_base_id == kb_id,
                KBPermission.user_id == user.id,
            )
        )
        return permission.role if permission else None

    def can_view_kb(self, user: User, kb_id: UUID) -> bool:
        return self.role_for_kb(user, kb_id) is not None

    def can_edit_kb(self, user: User, kb_id: UUID) -> bool:
        role = self.role_for_kb(user, kb_id)
        return role is not None and ROLE_RANK[role] >= ROLE_RANK[KBPermissionRole.editor]

    def can_manage_kb(self, user: User, kb_id: UUID) -> bool:
        role = self.role_for_kb(user, kb_id)
        return role == KBPermissionRole.owner

    def filter_accessible_kb_ids(self, user: User, kb_ids: list[UUID]) -> list[UUID]:
        if user.role == UserRole.admin:
            existing = self.db.scalars(
                select(KnowledgeBase.id).where(KnowledgeBase.id.in_(kb_ids))
            ).all()
            return list(existing)
        return [kb_id for kb_id in kb_ids if self.can_view_kb(user, kb_id)]

    def require_kb_permission(
        self,
        user: User,
        kb_id: UUID,
        required_role: KBPermissionRole,
    ) -> KBPermissionRole:
        role = self.role_for_kb(user, kb_id)
        if role is None or ROLE_RANK[role] < ROLE_RANK[required_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Knowledge base {required_role.value} permission required",
            )
        return role

    def require_manage_kb(self, user: User, kb_id: UUID) -> None:
        if not self.can_manage_kb(user, kb_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Knowledge base owner permission required",
            )

    def owner_count(self, kb_id: UUID) -> int:
        return int(
            self.db.scalar(
                select(func.count(KBPermission.id)).where(
                    KBPermission.knowledge_base_id == kb_id,
                    KBPermission.role == KBPermissionRole.owner,
                )
            )
            or 0
        )

    def ensure_can_change_permission(
        self,
        permission: KBPermission,
        new_role: KBPermissionRole | None = None,
        deleting: bool = False,
    ) -> None:
        if permission.role != KBPermissionRole.owner:
            return
        if not deleting and new_role == KBPermissionRole.owner:
            return
        if self.owner_count(permission.knowledge_base_id) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove or downgrade the last owner",
            )


def can_view_kb(db: Session, user: User, kb_id: UUID) -> bool:
    return PermissionService(db).can_view_kb(user, kb_id)


def can_edit_kb(db: Session, user: User, kb_id: UUID) -> bool:
    return PermissionService(db).can_edit_kb(user, kb_id)


def can_manage_kb(db: Session, user: User, kb_id: UUID) -> bool:
    return PermissionService(db).can_manage_kb(user, kb_id)


def filter_accessible_kb_ids(db: Session, user: User, kb_ids: list[UUID]) -> list[UUID]:
    return PermissionService(db).filter_accessible_kb_ids(user, kb_ids)


def require_kb_permission(
    db: Session,
    user: User,
    kb_id: UUID,
    required_role: KBPermissionRole,
) -> KBPermissionRole:
    return PermissionService(db).require_kb_permission(user, kb_id, required_role)
