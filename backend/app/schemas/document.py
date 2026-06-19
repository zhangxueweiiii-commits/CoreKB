from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    filename: str
    file_path: str
    file_type: str
    file_size: int
    status: DocumentStatus
    error_message: str | None = None
    chunk_count: int
    meta: dict = Field(default_factory=dict)
    metadata_completeness: dict | None = None
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentMetadataSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    field: str
    raw_value: str
    normalized_value: str
    normalization_source: str
    dictionary_entry_id: UUID | None = None
    custom_value: bool = False
    suggested_value: str
    confidence: str
    source: str
    evidence_excerpt: str
    rule_name: str
    status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    current_value: str | None = None
    review_guardrails: dict = Field(default_factory=dict)


class DocumentMetadataSuggestionAcceptRequest(BaseModel):
    value: str | None = None
    custom_value: bool = False


class DocumentMetadataSuggestionListResponse(BaseModel):
    items: list[DocumentMetadataSuggestionRead] = Field(default_factory=list)
    total: int


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    chunk_text: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    meta: dict
    created_at: datetime
