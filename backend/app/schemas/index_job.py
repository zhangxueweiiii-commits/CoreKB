from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.index_job import IndexJobItemStatus, IndexJobStatus, IndexJobType


class ReindexRequest(BaseModel):
    document_ids: list[UUID] | None = None
    force: bool = True


class IndexJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: IndexJobType
    status: IndexJobStatus
    knowledge_base_id: UUID
    document_id: UUID | None = None
    created_by: UUID | None = None
    total_count: int
    success_count: int
    failed_count: int
    pending_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class IndexJobItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    filename: str | None = None
    status: IndexJobItemStatus
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class IndexJobDetail(IndexJobSummary):
    error_message: str | None = None
    items: list[IndexJobItemRead] = Field(default_factory=list)


class IndexJobStats(BaseModel):
    running_count: int
    pending_count: int
    completed_count: int
    partial_failed_count: int
    failed_count: int
    failed_recent_count: int
    latest_failed_jobs: list[IndexJobSummary]


class IndexJobActionResponse(BaseModel):
    message: str
    job: IndexJobSummary | None = None
