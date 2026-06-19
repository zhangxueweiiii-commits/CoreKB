"""add document metadata suggestions

Revision ID: 0017_document_metadata_suggestions
Revises: 0016_evaluation_improvement_case_results
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0017_document_metadata_suggestions"
down_revision: str | None = "0016_evaluation_improvement_case_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


suggestion_confidence_enum = postgresql.ENUM(
    "high",
    "medium",
    "low",
    name="documentmetadatasuggestionconfidence",
)
suggestion_source_enum = postgresql.ENUM(
    "filename",
    "title",
    "parsed_text",
    name="documentmetadatasuggestionsource",
)
suggestion_status_enum = postgresql.ENUM(
    "pending",
    "accepted",
    "rejected",
    name="documentmetadatasuggestionstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    suggestion_confidence_enum.create(bind, checkfirst=True)
    suggestion_source_enum.create(bind, checkfirst=True)
    suggestion_status_enum.create(bind, checkfirst=True)
    op.create_table(
        "document_metadata_suggestions",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column("suggested_value", sa.String(length=255), nullable=False),
        sa.Column("confidence", suggestion_confidence_enum, nullable=False),
        sa.Column("source", suggestion_source_enum, nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=False),
        sa.Column("rule_name", sa.String(length=128), nullable=False),
        sa.Column("status", suggestion_status_enum, nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "field", "suggested_value", name="uq_document_metadata_suggestion_value"),
    )
    op.create_index("ix_document_metadata_suggestions_document_id", "document_metadata_suggestions", ["document_id"])
    op.create_index("ix_document_metadata_suggestions_field", "document_metadata_suggestions", ["field"])
    op.create_index("ix_document_metadata_suggestions_confidence", "document_metadata_suggestions", ["confidence"])
    op.create_index("ix_document_metadata_suggestions_source", "document_metadata_suggestions", ["source"])
    op.create_index("ix_document_metadata_suggestions_status", "document_metadata_suggestions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_document_metadata_suggestions_status", table_name="document_metadata_suggestions")
    op.drop_index("ix_document_metadata_suggestions_source", table_name="document_metadata_suggestions")
    op.drop_index("ix_document_metadata_suggestions_confidence", table_name="document_metadata_suggestions")
    op.drop_index("ix_document_metadata_suggestions_field", table_name="document_metadata_suggestions")
    op.drop_index("ix_document_metadata_suggestions_document_id", table_name="document_metadata_suggestions")
    op.drop_table("document_metadata_suggestions")
    bind = op.get_bind()
    suggestion_status_enum.drop(bind, checkfirst=True)
    suggestion_source_enum.drop(bind, checkfirst=True)
    suggestion_confidence_enum.drop(bind, checkfirst=True)
