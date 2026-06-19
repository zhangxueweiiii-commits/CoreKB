"""evaluation runs

Revision ID: 0008_evaluation_runs
Revises: 0007_alert_events
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_evaluation_runs"
down_revision: str | None = "0007_alert_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


evaluation_type = postgresql.ENUM("retrieval", name="evaluationtype", create_type=False)


def upgrade() -> None:
    evaluation_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eval_type", evaluation_type, nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failed_cases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_eval_type", "evaluation_runs", ["eval_type"])
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_eval_type", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    evaluation_type.drop(op.get_bind(), checkfirst=True)
