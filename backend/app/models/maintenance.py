import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class MaintenanceRecordDraftStatus(str, enum.Enum):
    draft = "draft"


class MaintenanceExperienceCandidateStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class MaintenanceKnowledgeEntryStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class MaintenanceRecordDraft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "maintenance_record_drafts"

    equipment_model: Mapped[str | None] = mapped_column(String(120), index=True)
    fault_symptom: Mapped[str] = mapped_column(Text, nullable=False)
    fault_code: Mapped[str | None] = mapped_column(String(80), index=True)
    assistant_answer_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    selected_evidence_snapshot: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    citation_metadata: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    metadata_filter_used: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rerank_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MaintenanceRecordDraftStatus] = mapped_column(
        Enum(MaintenanceRecordDraftStatus),
        default=MaintenanceRecordDraftStatus.draft,
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MaintenanceExperienceCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "maintenance_experience_candidates"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_model: Mapped[str | None] = mapped_column(String(120), index=True)
    fault_code: Mapped[str | None] = mapped_column(String(80), index=True)
    fault_symptom: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_candidate: Mapped[str | None] = mapped_column(Text)
    effective_handling_method: Mapped[str] = mapped_column(Text, nullable=False)
    ineffective_handling_method: Mapped[str | None] = mapped_column(Text)
    spare_parts_involved: Mapped[str | None] = mapped_column(Text)
    safety_notes: Mapped[str | None] = mapped_column(Text)
    applicable_scope: Mapped[str | None] = mapped_column(Text)
    evidence_references: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_record_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_record_drafts.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[MaintenanceExperienceCandidateStatus] = mapped_column(
        Enum(MaintenanceExperienceCandidateStatus),
        default=MaintenanceExperienceCandidateStatus.pending,
        nullable=False,
        index=True,
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source_record_draft = relationship("MaintenanceRecordDraft")


class MaintenanceKnowledgeEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "maintenance_knowledge_entries"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_model: Mapped[str | None] = mapped_column(String(120), index=True)
    fault_code: Mapped[str | None] = mapped_column(String(80), index=True)
    fault_symptom: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    spare_parts: Mapped[str | None] = mapped_column(Text)
    evidence_references: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_experience_candidates.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[MaintenanceKnowledgeEntryStatus] = mapped_column(
        Enum(MaintenanceKnowledgeEntryStatus),
        default=MaintenanceKnowledgeEntryStatus.active,
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_candidate = relationship("MaintenanceExperienceCandidate")
