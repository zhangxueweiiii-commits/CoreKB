import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class EvaluationType(str, enum.Enum):
    retrieval = "retrieval"
    assistant = "assistant"


class EvaluationRun(Base, UUIDMixin):
    __tablename__ = "evaluation_runs"

    eval_type: Mapped[EvaluationType] = mapped_column(Enum(EvaluationType), nullable=False, index=True)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    failed_cases: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    run_label: Mapped[str | None] = mapped_column(Text)
    change_type: Mapped[str | None] = mapped_column(Text, index=True)
    change_summary: Mapped[str | None] = mapped_column(Text)
    operator_notes: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvaluationCaseResult(Base, UUIDMixin):
    __tablename__ = "evaluation_case_results"

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    assistant_type: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected_document: Mapped[str | None] = mapped_column(Text)
    expected_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    expected_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    should_have_answer: Mapped[bool] = mapped_column(default=True, nullable=False)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    suggested_fix_type: Mapped[str | None] = mapped_column(Text)
    used_metadata_filter: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    use_rerank: Mapped[bool] = mapped_column(default=False, nullable=False)
    rerank_applied: Mapped[bool] = mapped_column(default=False, nullable=False)
    answer_excerpt: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    retrieved_results: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
