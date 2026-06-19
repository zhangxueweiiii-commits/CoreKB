from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogRead
from app.services.audit_service import apply_audit_filters, audit_query
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    knowledge_base_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    if current_user.role == UserRole.viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit log access denied")
    stmt = audit_query()
    stmt = apply_audit_filters(
        stmt,
        action=action,
        resource_type=resource_type,
        knowledge_base_id=knowledge_base_id,
        actor_user_id=actor_user_id,
        start_time=start_time,
        end_time=end_time,
    )
    if current_user.role != UserRole.admin:
        if knowledge_base_id:
            if not PermissionService(db).can_manage_kb(current_user, knowledge_base_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audit log access denied")
        else:
            rows = db.query(AuditLog.knowledge_base_id).distinct().all()
            kb_ids = [row[0] for row in rows if row[0]]
            manageable = [
                kb_id for kb_id in kb_ids if PermissionService(db).can_manage_kb(current_user, kb_id)
            ]
            if not manageable:
                return []
            stmt = stmt.where(AuditLog.knowledge_base_id.in_(manageable))
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())
