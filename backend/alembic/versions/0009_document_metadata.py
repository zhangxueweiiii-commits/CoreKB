"""document metadata

Revision ID: 0009_document_metadata
Revises: 0008_evaluation_runs
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_document_metadata"
down_revision: str | None = "0008_evaluation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("documents", "metadata", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "metadata")
