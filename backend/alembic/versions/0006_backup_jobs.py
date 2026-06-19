"""backup jobs

Revision ID: 0006_backup_jobs
Revises: 0005_audit_observability_pause
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_backup_jobs"
down_revision: str | None = "0005_audit_observability_pause"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


backup_job_type = postgresql.ENUM("postgres", "qdrant", "uploads", "all", name="backupjobtype", create_type=False)
backup_job_status = postgresql.ENUM("running", "completed", "failed", name="backupjobstatus", create_type=False)


def upgrade() -> None:
    backup_job_type.create(op.get_bind(), checkfirst=True)
    backup_job_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "backup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", backup_job_type, nullable=False),
        sa.Column("status", backup_job_status, nullable=False),
        sa.Column("backup_path", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_jobs_created_at", "backup_jobs", ["created_at"])
    op.create_index("ix_backup_jobs_status", "backup_jobs", ["status"])
    op.create_index("ix_backup_jobs_job_type", "backup_jobs", ["job_type"])


def downgrade() -> None:
    op.drop_index("ix_backup_jobs_job_type", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_status", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_created_at", table_name="backup_jobs")
    op.drop_table("backup_jobs")
    backup_job_status.drop(op.get_bind(), checkfirst=True)
    backup_job_type.drop(op.get_bind(), checkfirst=True)
