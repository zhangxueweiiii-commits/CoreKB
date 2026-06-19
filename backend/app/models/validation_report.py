import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ValidationReportType(str, enum.Enum):
    metadata = "metadata"


class ValidationReportSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"


class ValidationReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    ignored = "ignored"


class ValidationReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_reports"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[ValidationReportType] = mapped_column(
        Enum(ValidationReportType), default=ValidationReportType.metadata, nullable=False, index=True
    )
    severity: Mapped[ValidationReportSeverity] = mapped_column(
        Enum(ValidationReportSeverity), default=ValidationReportSeverity.info, nullable=False, index=True
    )
    issue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issues_json: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ValidationReportStatus] = mapped_column(
        Enum(ValidationReportStatus), default=ValidationReportStatus.open, nullable=False, index=True
    )

    document = relationship("Document")
