import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class FailureTriageStatus(str, enum.Enum):
    open = "open"
    reviewing = "reviewing"
    resolved = "resolved"
    ignored = "ignored"


class EvaluationFailureTriageNote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_failure_triage_notes"
    __table_args__ = (
        UniqueConstraint("evaluation_case_result_id", name="uq_evaluation_failure_triage_notes_case_result"),
    )

    evaluation_case_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_case_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triage_status: Mapped[FailureTriageStatus] = mapped_column(
        Enum(FailureTriageStatus),
        default=FailureTriageStatus.open,
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
