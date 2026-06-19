from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetadataDictionaryEntryCreate(BaseModel):
    field_name: str
    canonical_value: str
    aliases: list[str] = Field(default_factory=list)
    status: str = "active"
    description: str | None = None


class MetadataDictionaryEntryUpdate(BaseModel):
    canonical_value: str | None = None
    aliases: list[str] | None = None
    status: str | None = None
    description: str | None = None


class MetadataDictionaryAliasRequest(BaseModel):
    alias: str


class MetadataDictionaryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_name: str
    canonical_value: str
    aliases: list[str]
    status: str
    description: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
