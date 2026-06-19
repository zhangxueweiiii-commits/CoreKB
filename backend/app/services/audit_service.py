from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.request_context import get_request_context
from app.models.audit_log import AuditLog
from app.models.user import User


SENSITIVE_KEYS = {"password", "api_key", "secret", "token", "authorization", "file_content", "content"}
MAX_AUDIT_STRING_LENGTH = 500


def _sanitize_metadata(metadata: dict | None) -> dict:
    if not metadata:
        return {}
    return {
        str(key): _sanitize_value(str(key), value)
        for key, value in metadata.items()
    }


def _sanitize_value(key: str, value):
    if key.lower() in SENSITIVE_KEYS:
        return "[redacted]"
    if isinstance(value, str):
        return value[:MAX_AUDIT_STRING_LENGTH]
    if isinstance(value, Mapping):
        return {str(child_key): _sanitize_value(str(child_key), child_value) for child_key, child_value in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value("", item) for item in value]
    return value


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        actor: User | None,
        action: str,
        resource_type: str,
        resource_id: str | UUID | None = None,
        knowledge_base_id: UUID | None = None,
        document_id: UUID | None = None,
        status: str = "success",
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        context = get_request_context()
        log = AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
            status=status,
            error_message=error_message[:2000] if error_message else None,
            meta=_sanitize_metadata(metadata),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log


def audit_query() -> Select[tuple[AuditLog]]:
    return select(AuditLog).order_by(AuditLog.created_at.desc())


def apply_audit_filters(
    stmt,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    knowledge_base_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if knowledge_base_id:
        stmt = stmt.where(AuditLog.knowledge_base_id == knowledge_base_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if start_time:
        stmt = stmt.where(AuditLog.created_at >= start_time)
    if end_time:
        stmt = stmt.where(AuditLog.created_at <= end_time)
    return stmt
