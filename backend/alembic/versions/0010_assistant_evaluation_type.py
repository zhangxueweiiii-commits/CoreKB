"""assistant evaluation type

Revision ID: 0010_assistant_evaluation_type
Revises: 0009_document_metadata
Create Date: 2026-06-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_assistant_evaluation_type"
down_revision: str | None = "0009_document_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE evaluationtype ADD VALUE IF NOT EXISTS 'assistant'")


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values directly.
    pass
