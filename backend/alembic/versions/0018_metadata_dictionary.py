"""add metadata dictionary and suggestion normalization fields

Revision ID: 0018_metadata_dictionary
Revises: 0017_document_metadata_suggestions
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0018_metadata_dictionary"
down_revision: str | None = "0017_document_metadata_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


dictionary_status_enum = postgresql.ENUM(
    "active",
    "inactive",
    name="metadatadictionaryentrystatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    dictionary_status_enum.create(bind, checkfirst=True)
    op.create_table(
        "metadata_dictionary_entries",
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("canonical_value", sa.String(length=255), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", dictionary_status_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_name", "canonical_value", name="uq_metadata_dictionary_field_canonical"),
    )
    op.create_index("ix_metadata_dictionary_entries_field_name", "metadata_dictionary_entries", ["field_name"])
    op.create_index("ix_metadata_dictionary_entries_status", "metadata_dictionary_entries", ["status"])

    op.add_column(
        "document_metadata_suggestions",
        sa.Column("raw_value", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "document_metadata_suggestions",
        sa.Column("normalized_value", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "document_metadata_suggestions",
        sa.Column("normalization_source", sa.String(length=64), server_default="rule", nullable=False),
    )
    op.add_column(
        "document_metadata_suggestions",
        sa.Column("dictionary_entry_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "document_metadata_suggestions",
        sa.Column("custom_value", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute("UPDATE document_metadata_suggestions SET raw_value = suggested_value WHERE raw_value = ''")
    op.execute("UPDATE document_metadata_suggestions SET normalized_value = suggested_value WHERE normalized_value = ''")
    op.create_foreign_key(
        "fk_document_metadata_suggestions_dictionary_entry_id",
        "document_metadata_suggestions",
        "metadata_dictionary_entries",
        ["dictionary_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_metadata_suggestions_dictionary_entry_id",
        "document_metadata_suggestions",
        ["dictionary_entry_id"],
    )
    op.alter_column("document_metadata_suggestions", "raw_value", server_default=None)
    op.alter_column("document_metadata_suggestions", "normalized_value", server_default=None)
    op.alter_column("document_metadata_suggestions", "normalization_source", server_default=None)
    op.alter_column("document_metadata_suggestions", "custom_value", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_document_metadata_suggestions_dictionary_entry_id", table_name="document_metadata_suggestions")
    op.drop_constraint(
        "fk_document_metadata_suggestions_dictionary_entry_id",
        "document_metadata_suggestions",
        type_="foreignkey",
    )
    op.drop_column("document_metadata_suggestions", "custom_value")
    op.drop_column("document_metadata_suggestions", "dictionary_entry_id")
    op.drop_column("document_metadata_suggestions", "normalization_source")
    op.drop_column("document_metadata_suggestions", "normalized_value")
    op.drop_column("document_metadata_suggestions", "raw_value")

    op.drop_index("ix_metadata_dictionary_entries_status", table_name="metadata_dictionary_entries")
    op.drop_index("ix_metadata_dictionary_entries_field_name", table_name="metadata_dictionary_entries")
    op.drop_table("metadata_dictionary_entries")
    dictionary_status_enum.drop(op.get_bind(), checkfirst=True)
