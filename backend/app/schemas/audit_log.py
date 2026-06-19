from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    knowledge_base_id: UUID | None
    document_id: UUID | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    status: str
    error_message: str | None
    meta: dict
    created_at: datetime
