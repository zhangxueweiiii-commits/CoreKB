from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.knowledge_base import KBPermissionRole, KnowledgeBaseVisibility


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    visibility: KnowledgeBaseVisibility = KnowledgeBaseVisibility.private


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    visibility: KnowledgeBaseVisibility | None = None


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    visibility: KnowledgeBaseVisibility
    access_role: KBPermissionRole | None = None
    created_at: datetime
    updated_at: datetime


class KBPermissionCreate(BaseModel):
    user_id: UUID
    role: KBPermissionRole


class KBPermissionUpdate(BaseModel):
    role: KBPermissionRole


class KBPermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    user_id: UUID
    role: KBPermissionRole
    created_by: UUID | None
    username: str
    email: str | None = None
    created_at: datetime
    updated_at: datetime
