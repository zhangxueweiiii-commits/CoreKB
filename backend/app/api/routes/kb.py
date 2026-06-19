from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import assert_can_edit_kb, assert_can_manage_kb, assert_can_view_kb, get_current_user, get_kb_or_404
from app.db.session import get_db
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.models.document import Document
from app.schemas.kb import (
    KBPermissionCreate,
    KBPermissionRead,
    KBPermissionUpdate,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
)
from app.schemas.index_job import IndexJobSummary, ReindexRequest
from app.core.metrics import INDEX_JOBS_TOTAL
from app.services.audit_service import AuditService
from app.services.index_job_service import IndexJobService
from app.services.permission_service import PermissionService
from app.tasks.document_tasks import enqueue_reindex_job

router = APIRouter(prefix="/kb", tags=["knowledge bases"])


def _read_kb(db: Session, user: User, kb: KnowledgeBase) -> KnowledgeBaseRead:
    data = KnowledgeBaseRead.model_validate(kb)
    return data.model_copy(update={"access_role": PermissionService(db).role_for_kb(user, kb.id)})


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeBaseRead]:
    if current_user.role == UserRole.admin:
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    else:
        stmt = (
            select(KnowledgeBase)
            .join(KBPermission, KBPermission.knowledge_base_id == KnowledgeBase.id)
            .where(KBPermission.user_id == current_user.id)
            .order_by(KnowledgeBase.created_at.desc())
            .distinct()
        )
    return [_read_kb(db, current_user, kb) for kb in db.scalars(stmt).all()]


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeBaseRead:
    if current_user.role == UserRole.viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewer cannot create knowledge bases")
    kb = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
        owner_id=current_user.id,
    )
    db.add(kb)
    db.flush()
    db.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=current_user.id,
            role=KBPermissionRole.owner,
            created_by=current_user.id,
        )
    )
    db.commit()
    db.refresh(kb)
    AuditService(db).record(
        actor=current_user,
        action="kb.create",
        resource_type="knowledge_base",
        resource_id=kb.id,
        knowledge_base_id=kb.id,
        status="success",
        metadata={"name": kb.name},
    )
    return _read_kb(db, current_user, kb)


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeBaseRead:
    kb = get_kb_or_404(db, kb_id)
    assert_can_view_kb(db, current_user, kb)
    return _read_kb(db, current_user, kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    kb_id: UUID,
    payload: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeBaseRead:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(kb, key, value)
    db.commit()
    db.refresh(kb)
    AuditService(db).record(
        actor=current_user,
        action="kb.update",
        resource_type="knowledge_base",
        resource_id=kb.id,
        knowledge_base_id=kb.id,
        status="success",
        metadata={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return _read_kb(db, current_user, kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    AuditService(db).record(
        actor=current_user,
        action="kb.delete",
        resource_type="knowledge_base",
        resource_id=kb.id,
        knowledge_base_id=kb.id,
        status="success",
        metadata={"name": kb.name},
    )
    db.delete(kb)
    db.commit()


@router.post("/{kb_id}/reindex", response_model=IndexJobSummary, status_code=status.HTTP_202_ACCEPTED)
def reindex_knowledge_base(
    kb_id: UUID,
    payload: ReindexRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobSummary:
    kb = get_kb_or_404(db, kb_id)
    assert_can_edit_kb(db, current_user, kb)
    payload = payload or ReindexRequest()
    stmt = select(Document).where(Document.knowledge_base_id == kb_id)
    if payload.document_ids:
        stmt = stmt.where(Document.id.in_(payload.document_ids))
    documents = list(db.scalars(stmt.order_by(Document.created_at.asc())).all())
    if payload.document_ids and len(documents) != len(set(payload.document_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more documents were not found in this knowledge base",
        )
    job = IndexJobService(db).create_kb_reindex_job(kb_id, documents, current_user, payload.force)
    enqueue_reindex_job(job.id)
    INDEX_JOBS_TOTAL.labels(job.job_type.value).inc()
    AuditService(db).record(
        actor=current_user,
        action="kb.reindex",
        resource_type="index_job",
        resource_id=job.id,
        knowledge_base_id=kb_id,
        status="success",
        metadata={"total_count": job.total_count, "force": payload.force},
    )
    return job


@router.get("/{kb_id}/permissions", response_model=list[KBPermissionRead])
def list_permissions(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KBPermissionRead]:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    rows = db.execute(
        select(KBPermission, User)
        .join(User, User.id == KBPermission.user_id)
        .where(KBPermission.knowledge_base_id == kb_id)
        .order_by(KBPermission.created_at.asc())
    ).all()
    return [
        KBPermissionRead(
            id=permission.id,
            knowledge_base_id=permission.knowledge_base_id,
            user_id=permission.user_id,
            role=permission.role,
            created_by=permission.created_by,
            username=user.username,
            email=user.email,
            created_at=permission.created_at,
            updated_at=permission.updated_at,
        )
        for permission, user in rows
    ]


@router.post("/{kb_id}/permissions", response_model=KBPermissionRead, status_code=status.HTTP_201_CREATED)
def create_permission(
    kb_id: UUID,
    payload: KBPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KBPermissionRead:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    target_user = db.get(User, payload.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    exists = db.scalar(
        select(KBPermission).where(
            KBPermission.knowledge_base_id == kb_id,
            KBPermission.user_id == payload.user_id,
        )
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Permission already exists")
    permission = KBPermission(
        knowledge_base_id=kb_id,
        user_id=payload.user_id,
        role=payload.role,
        created_by=current_user.id,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    AuditService(db).record(
        actor=current_user,
        action="kb.permission.add",
        resource_type="kb_permission",
        resource_id=permission.id,
        knowledge_base_id=kb_id,
        status="success",
        metadata={"target_user_id": str(payload.user_id), "role": payload.role.value},
    )
    return KBPermissionRead(
        id=permission.id,
        knowledge_base_id=permission.knowledge_base_id,
        user_id=permission.user_id,
        role=permission.role,
        created_by=permission.created_by,
        username=target_user.username,
        email=target_user.email,
        created_at=permission.created_at,
        updated_at=permission.updated_at,
    )


@router.patch("/{kb_id}/permissions/{permission_id}", response_model=KBPermissionRead)
def update_permission(
    kb_id: UUID,
    permission_id: UUID,
    payload: KBPermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KBPermissionRead:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    permission = db.get(KBPermission, permission_id)
    if not permission or permission.knowledge_base_id != kb_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    PermissionService(db).ensure_can_change_permission(permission, new_role=payload.role)
    permission.role = payload.role
    db.commit()
    db.refresh(permission)
    target_user = db.get(User, permission.user_id)
    AuditService(db).record(
        actor=current_user,
        action="kb.permission.update",
        resource_type="kb_permission",
        resource_id=permission.id,
        knowledge_base_id=kb_id,
        status="success",
        metadata={"target_user_id": str(permission.user_id), "role": payload.role.value},
    )
    return KBPermissionRead(
        id=permission.id,
        knowledge_base_id=permission.knowledge_base_id,
        user_id=permission.user_id,
        role=permission.role,
        created_by=permission.created_by,
        username=target_user.username if target_user else "",
        email=target_user.email if target_user else None,
        created_at=permission.created_at,
        updated_at=permission.updated_at,
    )


@router.delete("/{kb_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    kb_id: UUID,
    permission_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    kb = get_kb_or_404(db, kb_id)
    assert_can_manage_kb(db, current_user, kb)
    permission = db.get(KBPermission, permission_id)
    if not permission or permission.knowledge_base_id != kb_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    PermissionService(db).ensure_can_change_permission(permission, deleting=True)
    AuditService(db).record(
        actor=current_user,
        action="kb.permission.remove",
        resource_type="kb_permission",
        resource_id=permission.id,
        knowledge_base_id=kb_id,
        status="success",
        metadata={"target_user_id": str(permission.user_id), "role": permission.role.value},
    )
    db.delete(permission)
    db.commit()
