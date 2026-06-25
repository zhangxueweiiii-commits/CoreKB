"""add maintenance curation tables

Revision ID: 0021_maintenance_curation
Revises: 0020_evaluation_failure_triage_notes
Create Date: 2026-06-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0021_maintenance_curation"
down_revision: str | None = "0020_evaluation_failure_triage_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


record_status_enum = postgresql.ENUM("draft", name="maintenancerecorddraftstatus")
candidate_status_enum = postgresql.ENUM("pending", "accepted", "rejected", name="maintenanceexperiencecandidatestatus")
entry_status_enum = postgresql.ENUM("active", "inactive", name="maintenanceknowledgeentrystatus")


def upgrade() -> None:
    bind = op.get_bind()
    record_status_enum.create(bind, checkfirst=True)
    candidate_status_enum.create(bind, checkfirst=True)
    entry_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "maintenance_record_drafts",
        sa.Column("equipment_model", sa.String(length=120), nullable=True),
        sa.Column("fault_symptom", sa.Text(), nullable=False),
        sa.Column("fault_code", sa.String(length=80), nullable=True),
        sa.Column("assistant_answer_snapshot", sa.Text(), nullable=False),
        sa.Column("selected_evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("citation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_filter_used", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rerank_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("status", record_status_enum, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_record_drafts_equipment_model", "maintenance_record_drafts", ["equipment_model"])
    op.create_index("ix_maintenance_record_drafts_fault_code", "maintenance_record_drafts", ["fault_code"])
    op.create_index("ix_maintenance_record_drafts_status", "maintenance_record_drafts", ["status"])

    op.create_table(
        "maintenance_experience_candidates",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("equipment_model", sa.String(length=120), nullable=True),
        sa.Column("fault_code", sa.String(length=80), nullable=True),
        sa.Column("fault_symptom", sa.Text(), nullable=False),
        sa.Column("root_cause_candidate", sa.Text(), nullable=True),
        sa.Column("effective_handling_method", sa.Text(), nullable=False),
        sa.Column("ineffective_handling_method", sa.Text(), nullable=True),
        sa.Column("spare_parts_involved", sa.Text(), nullable=True),
        sa.Column("safety_notes", sa.Text(), nullable=True),
        sa.Column("applicable_scope", sa.Text(), nullable=True),
        sa.Column("evidence_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_record_draft_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", candidate_status_enum, nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_record_draft_id"], ["maintenance_record_drafts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_experience_candidates_equipment_model", "maintenance_experience_candidates", ["equipment_model"])
    op.create_index("ix_maintenance_experience_candidates_fault_code", "maintenance_experience_candidates", ["fault_code"])
    op.create_index("ix_maintenance_experience_candidates_status", "maintenance_experience_candidates", ["status"])

    op.create_table(
        "maintenance_knowledge_entries",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("equipment_model", sa.String(length=120), nullable=True),
        sa.Column("fault_code", sa.String(length=80), nullable=True),
        sa.Column("fault_symptom", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("spare_parts", sa.Text(), nullable=True),
        sa.Column("evidence_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", entry_status_enum, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["maintenance_experience_candidates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_knowledge_entries_equipment_model", "maintenance_knowledge_entries", ["equipment_model"])
    op.create_index("ix_maintenance_knowledge_entries_fault_code", "maintenance_knowledge_entries", ["fault_code"])
    op.create_index("ix_maintenance_knowledge_entries_status", "maintenance_knowledge_entries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_knowledge_entries_status", table_name="maintenance_knowledge_entries")
    op.drop_index("ix_maintenance_knowledge_entries_fault_code", table_name="maintenance_knowledge_entries")
    op.drop_index("ix_maintenance_knowledge_entries_equipment_model", table_name="maintenance_knowledge_entries")
    op.drop_table("maintenance_knowledge_entries")
    op.drop_index("ix_maintenance_experience_candidates_status", table_name="maintenance_experience_candidates")
    op.drop_index("ix_maintenance_experience_candidates_fault_code", table_name="maintenance_experience_candidates")
    op.drop_index("ix_maintenance_experience_candidates_equipment_model", table_name="maintenance_experience_candidates")
    op.drop_table("maintenance_experience_candidates")
    op.drop_index("ix_maintenance_record_drafts_status", table_name="maintenance_record_drafts")
    op.drop_index("ix_maintenance_record_drafts_fault_code", table_name="maintenance_record_drafts")
    op.drop_index("ix_maintenance_record_drafts_equipment_model", table_name="maintenance_record_drafts")
    op.drop_table("maintenance_record_drafts")
    entry_status_enum.drop(op.get_bind(), checkfirst=True)
    candidate_status_enum.drop(op.get_bind(), checkfirst=True)
    record_status_enum.drop(op.get_bind(), checkfirst=True)
