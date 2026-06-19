"""add validation reports

Revision ID: 0019_validation_reports
Revises: 0018_metadata_dictionary
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0019_validation_reports"
down_revision: str | None = "0018_metadata_dictionary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


report_type_enum = postgresql.ENUM("metadata", name="validationreporttype")
severity_enum = postgresql.ENUM("info", "warning", "error", name="validationreportseverity")
status_enum = postgresql.ENUM("open", "resolved", "ignored", name="validationreportstatus")


def upgrade() -> None:
    bind = op.get_bind()
    report_type_enum.create(bind, checkfirst=True)
    severity_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    op.create_table(
        "validation_reports",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("issues_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_reports_document_id", "validation_reports", ["document_id"])
    op.create_index("ix_validation_reports_report_type", "validation_reports", ["report_type"])
    op.create_index("ix_validation_reports_severity", "validation_reports", ["severity"])
    op.create_index("ix_validation_reports_status", "validation_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_validation_reports_status", table_name="validation_reports")
    op.drop_index("ix_validation_reports_severity", table_name="validation_reports")
    op.drop_index("ix_validation_reports_report_type", table_name="validation_reports")
    op.drop_index("ix_validation_reports_document_id", table_name="validation_reports")
    op.drop_table("validation_reports")
    status_enum.drop(op.get_bind(), checkfirst=True)
    severity_enum.drop(op.get_bind(), checkfirst=True)
    report_type_enum.drop(op.get_bind(), checkfirst=True)
