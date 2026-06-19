"""table parsing and retry/cancel job enums

Revision ID: 0004_table_retry_cancel
Revises: 0003_index_jobs
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_table_retry_cancel"
down_revision: str | None = "0003_index_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE indexjobtype ADD VALUE IF NOT EXISTS 'retry_failed'")
        op.execute("ALTER TYPE indexjobitemstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without recreating the enum.
    pass
