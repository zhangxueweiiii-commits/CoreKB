from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    knowledge_base_ids: list[UUID] = Field(min_length=1)
    conversation_id: UUID | None = None
    metadata_filter: dict | None = None
    auto_metadata_filter: bool = False
    use_rerank: bool = False
    rerank_top_n: int | None = Field(default=None, ge=1, le=100)


class Citation(BaseModel):
    filename: str
    page_number: int | None = None
    section_title: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    chunk_id: UUID
    quote: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: UUID
    used_metadata_filter: dict = Field(default_factory=dict)
    use_rerank: bool = False
    rerank_applied: bool = False
    rerank_error: str | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    citations: list[dict]
    knowledge_base_ids: list[str]
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    knowledge_base_ids: list[str]
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]
