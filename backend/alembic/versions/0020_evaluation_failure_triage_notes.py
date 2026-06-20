"""add evaluation failure triage notes

Revision ID: 0020_evaluation_failure_triage_notes
Revises: 0019_validation_reports
Create Date: 2026-06-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0020_evaluation_failure_triage_notes"
down_revision: str | None = "0019_validation_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


triage_status_enum = postgresql.ENUM(
    "open",
    "reviewing",
    "resolved",
    "ignored",
    name="failuretriagestatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    triage_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "evaluation_failure_triage_notes",
        sa.Column("evaluation_case_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triage_status", triage_status_enum, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evaluation_case_result_id"], ["evaluation_case_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_case_result_id", name="uq_evaluation_failure_triage_notes_case_result"),
    )
    op.create_index(
        "ix_evaluation_failure_triage_notes_evaluation_case_result_id",
        "evaluation_failure_triage_notes",
        ["evaluation_case_result_id"],
    )
    op.create_index(
        "ix_evaluation_failure_triage_notes_triage_status",
        "evaluation_failure_triage_notes",
        ["triage_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_failure_triage_notes_triage_status", table_name="evaluation_failure_triage_notes")
    op.drop_index(
        "ix_evaluation_failure_triage_notes_evaluation_case_result_id",
        table_name="evaluation_failure_triage_notes",
    )
    op.drop_table("evaluation_failure_triage_notes")
    triage_status_enum.drop(op.get_bind(), checkfirst=True)
