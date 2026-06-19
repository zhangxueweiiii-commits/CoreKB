"""permissions and async indexing

Revision ID: 0002_permissions_async
Revises: 0001_initial
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_permissions_async"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE kbpermissionrole ADD VALUE IF NOT EXISTS 'owner'")
        op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'chunking'")
        op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'indexed'")
    op.add_column("kb_permissions", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_kb_permissions_created_by_users",
        "kb_permissions",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "documents",
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute("UPDATE kb_permissions SET role = 'owner' WHERE role::text = 'admin'")
    op.execute("UPDATE documents SET status = 'indexed' WHERE status::text = 'ready'")
    op.execute(
        """
        UPDATE documents
        SET chunk_count = counts.chunk_count
        FROM (
            SELECT document_id, COUNT(*) AS chunk_count
            FROM document_chunks
            GROUP BY document_id
        ) AS counts
        WHERE documents.id = counts.document_id
        """
    )
    op.alter_column("documents", "chunk_count", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "indexed_at")
    op.drop_constraint("fk_kb_permissions_created_by_users", "kb_permissions", type_="foreignkey")
    op.drop_column("kb_permissions", "created_by")
