import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EvaluationImprovementStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    ignored = "ignored"


class EvaluationImprovementPriority(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class EvaluationImprovementRegressionStatus(str, enum.Enum):
    unverified = "unverified"
    passed = "passed"
    failed = "failed"


class EvaluationImprovementRelationSource(str, enum.Enum):
    system_rule = "system_rule"
    human_annotation = "human_annotation"
    manual_link = "manual_link"


class EvaluationImprovementItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_improvement_items"

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assistant_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    fix_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    priority: Mapped[EvaluationImprovementPriority] = mapped_column(
        Enum(EvaluationImprovementPriority), default=EvaluationImprovementPriority.medium, nullable=False, index=True
    )
    failed_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    affected_case_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    main_failure_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, default="system_rule", nullable=False, index=True)
    annotation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[EvaluationImprovementStatus] = mapped_column(
        Enum(EvaluationImprovementStatus), default=EvaluationImprovementStatus.open, nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    regression_status: Mapped[EvaluationImprovementRegressionStatus] = mapped_column(
        Enum(EvaluationImprovementRegressionStatus),
        default=EvaluationImprovementRegressionStatus.unverified,
        nullable=False,
        index=True,
    )
    related_regression_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_regressions.id", ondelete="SET NULL"), nullable=True
    )


class EvaluationImprovementItemCaseResult(Base, UUIDMixin):
    __tablename__ = "evaluation_improvement_item_case_results"
    __table_args__ = (
        UniqueConstraint(
            "improvement_item_id",
            "evaluation_case_result_id",
            name="uq_eval_improvement_item_case_result",
        ),
    )

    improvement_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_improvement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_case_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_case_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_source: Mapped[EvaluationImprovementRelationSource] = mapped_column(
        Enum(EvaluationImprovementRelationSource),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
