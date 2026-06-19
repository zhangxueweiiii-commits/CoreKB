import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class BackupJobType(str, enum.Enum):
    postgres = "postgres"
    qdrant = "qdrant"
    uploads = "uploads"
    all = "all"


class BackupJobStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class BackupJob(Base, UUIDMixin):
    __tablename__ = "backup_jobs"

    job_type: Mapped[BackupJobType] = mapped_column(Enum(BackupJobType), nullable=False)
    status: Mapped[BackupJobStatus] = mapped_column(Enum(BackupJobStatus), nullable=False)
    backup_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
