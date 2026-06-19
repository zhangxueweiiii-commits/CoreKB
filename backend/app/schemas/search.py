from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    knowledge_base_ids: list[UUID] = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    metadata_filter: dict | None = None
    use_rerank: bool = False
    rerank_top_n: int | None = Field(default=None, ge=1, le=100)


class SearchResult(BaseModel):
    chunk_text: str
    filename: str
    page_number: int | None = None
    score: float
    vector_score: float | None = None
    rerank_score: float | None = None
    final_score: float | None = None
    document_id: UUID
    chunk_id: UUID
    section_title: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    use_rerank: bool = False
    rerank_applied: bool = False
    rerank_error: str | None = None
