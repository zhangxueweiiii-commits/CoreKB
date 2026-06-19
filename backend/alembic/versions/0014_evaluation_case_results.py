"""evaluation case results

Revision ID: 0014_evaluation_case_results
Revises: 0013_evaluation_run_metadata
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_evaluation_case_results"
down_revision: str | None = "0013_evaluation_run_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_case_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("assistant_type", sa.Text(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_document", sa.Text(), nullable=True),
        sa.Column("expected_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("should_have_answer", sa.Boolean(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("suggested_fix_type", sa.Text(), nullable=True),
        sa.Column("used_metadata_filter", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("use_rerank", sa.Boolean(), nullable=False),
        sa.Column("rerank_applied", sa.Boolean(), nullable=False),
        sa.Column("answer_excerpt", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_case_results_evaluation_run_id", "evaluation_case_results", ["evaluation_run_id"])
    op.create_index("ix_evaluation_case_results_case_id", "evaluation_case_results", ["case_id"])
    op.create_index("ix_evaluation_case_results_assistant_type", "evaluation_case_results", ["assistant_type"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_case_results_assistant_type", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_case_id", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_evaluation_run_id", table_name="evaluation_case_results")
    op.drop_table("evaluation_case_results")
