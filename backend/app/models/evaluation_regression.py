import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class EvaluationRegression(Base, UUIDMixin):
    __tablename__ = "evaluation_regressions"

    before_evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    after_evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    improvement_item_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    assistant_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    fix_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    before_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    after_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    delta_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    affected_case_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    resolved_case_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    still_failed_case_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    regression_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
