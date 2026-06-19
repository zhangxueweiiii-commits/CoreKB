"""evaluation improvement items

Revision ID: 0011_evaluation_improvement_items
Revises: 0010_assistant_evaluation_type
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_evaluation_improvement_items"
down_revision: str | None = "0010_assistant_evaluation_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    priority_enum = postgresql.ENUM("high", "medium", "low", name="evaluationimprovementpriority")
    status_enum = postgresql.ENUM(
        "open", "in_progress", "resolved", "ignored", name="evaluationimprovementstatus"
    )
    priority_enum.create(op.get_bind(), checkfirst=True)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_improvement_items",
        sa.Column("evaluation_run_id", sa.UUID(), nullable=False),
        sa.Column("assistant_type", sa.Text(), nullable=False),
        sa.Column("fix_type", sa.Text(), nullable=False),
        sa.Column("priority", priority_enum, nullable=False),
        sa.Column("failed_case_count", sa.Integer(), nullable=False),
        sa.Column("affected_case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("main_failure_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_improvement_items_evaluation_run_id",
        "evaluation_improvement_items",
        ["evaluation_run_id"],
    )
    op.create_index(
        "ix_evaluation_improvement_items_assistant_type",
        "evaluation_improvement_items",
        ["assistant_type"],
    )
    op.create_index("ix_evaluation_improvement_items_fix_type", "evaluation_improvement_items", ["fix_type"])
    op.create_index("ix_evaluation_improvement_items_priority", "evaluation_improvement_items", ["priority"])
    op.create_index("ix_evaluation_improvement_items_status", "evaluation_improvement_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_improvement_items_status", table_name="evaluation_improvement_items")
    op.drop_index("ix_evaluation_improvement_items_priority", table_name="evaluation_improvement_items")
    op.drop_index("ix_evaluation_improvement_items_fix_type", table_name="evaluation_improvement_items")
    op.drop_index("ix_evaluation_improvement_items_assistant_type", table_name="evaluation_improvement_items")
    op.drop_index("ix_evaluation_improvement_items_evaluation_run_id", table_name="evaluation_improvement_items")
    op.drop_table("evaluation_improvement_items")
    postgresql.ENUM(name="evaluationimprovementstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="evaluationimprovementpriority").drop(op.get_bind(), checkfirst=True)
