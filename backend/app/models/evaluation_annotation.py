import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class HumanJudgement(str, enum.Enum):
    system_correct = "system_correct"
    system_partially_correct = "system_partially_correct"
    system_incorrect = "system_incorrect"
    business_expected_answer_wrong = "business_expected_answer_wrong"
    insufficient_documentation = "insufficient_documentation"
    needs_expert_review = "needs_expert_review"


class HumanRootCause(str, enum.Enum):
    prompt = "prompt"
    metadata_filter = "metadata_filter"
    document_metadata = "document_metadata"
    chunking = "chunking"
    rerank = "rerank"
    parser = "parser"
    source_document = "source_document"
    evaluation_case = "evaluation_case"
    business_rule = "business_rule"
    unknown = "unknown"


class HumanFixType(str, enum.Enum):
    update_prompt = "update_prompt"
    update_metadata = "update_metadata"
    update_chunking = "update_chunking"
    tune_rerank = "tune_rerank"
    improve_parser = "improve_parser"
    supplement_document = "supplement_document"
    revise_eval_case = "revise_eval_case"
    confirm_business_rule = "confirm_business_rule"
    no_action = "no_action"


class HandlingStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    planned = "planned"
    resolved = "resolved"
    ignored = "ignored"


class EvaluationCaseAnnotation(Base, UUIDMixin):
    __tablename__ = "evaluation_case_annotations"
    __table_args__ = (
        UniqueConstraint("evaluation_case_result_id", name="uq_evaluation_case_annotations_case_result"),
    )

    evaluation_case_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_case_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    human_judgement: Mapped[HumanJudgement] = mapped_column(Enum(HumanJudgement), nullable=False, index=True)
    human_root_cause: Mapped[HumanRootCause] = mapped_column(Enum(HumanRootCause), nullable=False, index=True)
    human_fix_type: Mapped[HumanFixType] = mapped_column(Enum(HumanFixType), nullable=False, index=True)
    handling_status: Mapped[HandlingStatus] = mapped_column(
        Enum(HandlingStatus), default=HandlingStatus.open, nullable=False, index=True
    )
    handling_notes: Mapped[str | None] = mapped_column(Text)
    annotated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    annotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
