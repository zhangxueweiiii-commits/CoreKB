from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat import Citation


class AssistantPresetRead(BaseModel):
    assistant_type: str
    display_name: str
    description: str
    system_prompt: str
    default_top_k: int
    default_rerank_top_n: int
    default_use_rerank: bool
    default_auto_metadata_filter: bool
    default_metadata_filter: dict
    answer_format: list[str]


class AssistantChatRequest(BaseModel):
    query: str = Field(min_length=1)
    metadata_filter: dict | None = None
    auto_metadata_filter: bool | None = None
    use_rerank: bool | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=100)
    top_k: int | None = Field(default=None, ge=1, le=20)
    conversation_id: UUID | None = None
    disable_preset_metadata_filter: bool = False


class AssistantChatResponse(BaseModel):
    assistant_type: str
    answer: str
    citations: list[Citation]
    used_metadata_filter: dict
    use_rerank: bool
    rerank_applied: bool
    rerank_error: str | None = None
    sources: list[Citation]
    no_answer_detected: bool
    conversation_id: UUID
    retrieved_results: list[dict] = Field(default_factory=list)
