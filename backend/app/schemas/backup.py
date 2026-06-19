from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.backup_job import BackupJobStatus, BackupJobType


class BackupJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: BackupJobType
    status: BackupJobStatus
    backup_path: str | None = None
    file_size: int | None = None
    checksum: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class BackupVerifyResponse(BaseModel):
    backup_id: UUID
    verified: bool
    expected_checksum: str | None = None
    actual_checksum: str | None = None
