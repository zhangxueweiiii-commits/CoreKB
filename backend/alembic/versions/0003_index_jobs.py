"""index jobs

Revision ID: 0003_index_jobs
Revises: 0002_permissions_async
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_index_jobs"
down_revision: str | None = "0002_permissions_async"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_type = postgresql.ENUM("document_index", "kb_reindex", name="indexjobtype", create_type=False)
    job_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "partial_failed",
        "failed",
        "cancelled",
        name="indexjobstatus",
        create_type=False,
    )
    item_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "skipped",
        name="indexjobitemstatus",
        create_type=False,
    )
    job_type.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "index_jobs",
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("pending_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_index_jobs_created_at", "index_jobs", ["created_at"])
    op.create_index("ix_index_jobs_kb_status", "index_jobs", ["knowledge_base_id", "status"])

    op.create_table(
        "index_job_items",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", item_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["index_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_index_job_items_job_status", "index_job_items", ["job_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_index_job_items_job_status", table_name="index_job_items")
    op.drop_table("index_job_items")
    op.drop_index("ix_index_jobs_kb_status", table_name="index_jobs")
    op.drop_index("ix_index_jobs_created_at", table_name="index_jobs")
    op.drop_table("index_jobs")
    for name in ("indexjobitemstatus", "indexjobstatus", "indexjobtype"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
