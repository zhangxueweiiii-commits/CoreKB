"""evaluation run metadata

Revision ID: 0013_evaluation_run_metadata
Revises: 0012_evaluation_regressions
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_evaluation_run_metadata"
down_revision: str | None = "0012_evaluation_regressions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evaluation_runs", sa.Column("run_label", sa.Text(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("change_type", sa.Text(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("change_summary", sa.Text(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("operator_notes", sa.Text(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_evaluation_runs_change_type", "evaluation_runs", ["change_type"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_change_type", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "config_snapshot")
    op.drop_column("evaluation_runs", "operator_notes")
    op.drop_column("evaluation_runs", "change_summary")
    op.drop_column("evaluation_runs", "change_type")
    op.drop_column("evaluation_runs", "run_label")
