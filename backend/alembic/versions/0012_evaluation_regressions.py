"""evaluation regressions

Revision ID: 0012_evaluation_regressions
Revises: 0011_evaluation_improvement_items
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_evaluation_regressions"
down_revision: str | None = "0011_evaluation_improvement_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    regression_status_enum = postgresql.ENUM(
        "unverified", "passed", "failed", name="evaluationimprovementregressionstatus"
    )
    regression_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_regressions",
        sa.Column("before_evaluation_run_id", sa.UUID(), nullable=False),
        sa.Column("after_evaluation_run_id", sa.UUID(), nullable=False),
        sa.Column("improvement_item_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assistant_type", sa.Text(), nullable=False),
        sa.Column("fix_type", sa.Text(), nullable=False),
        sa.Column("before_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("delta_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("affected_case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved_case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("still_failed_case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("regression_passed", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["after_evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["before_evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_regressions_after_evaluation_run_id", "evaluation_regressions", ["after_evaluation_run_id"])
    op.create_index("ix_evaluation_regressions_assistant_type", "evaluation_regressions", ["assistant_type"])
    op.create_index("ix_evaluation_regressions_before_evaluation_run_id", "evaluation_regressions", ["before_evaluation_run_id"])
    op.create_index("ix_evaluation_regressions_fix_type", "evaluation_regressions", ["fix_type"])
    op.create_index("ix_evaluation_regressions_regression_passed", "evaluation_regressions", ["regression_passed"])

    op.add_column("evaluation_improvement_items", sa.Column("resolved_evaluation_run_id", sa.UUID(), nullable=True))
    op.add_column(
        "evaluation_improvement_items",
        sa.Column(
            "regression_status",
            regression_status_enum,
            server_default="unverified",
            nullable=False,
        ),
    )
    op.add_column("evaluation_improvement_items", sa.Column("related_regression_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_evaluation_improvement_items_resolved_eval_run",
        "evaluation_improvement_items",
        "evaluation_runs",
        ["resolved_evaluation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_improvement_items_related_regression",
        "evaluation_improvement_items",
        "evaluation_regressions",
        ["related_regression_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_evaluation_improvement_items_regression_status",
        "evaluation_improvement_items",
        ["regression_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_improvement_items_regression_status", table_name="evaluation_improvement_items")
    op.drop_constraint(
        "fk_evaluation_improvement_items_related_regression",
        "evaluation_improvement_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_improvement_items_resolved_eval_run",
        "evaluation_improvement_items",
        type_="foreignkey",
    )
    op.drop_column("evaluation_improvement_items", "related_regression_id")
    op.drop_column("evaluation_improvement_items", "regression_status")
    op.drop_column("evaluation_improvement_items", "resolved_evaluation_run_id")

    op.drop_index("ix_evaluation_regressions_regression_passed", table_name="evaluation_regressions")
    op.drop_index("ix_evaluation_regressions_fix_type", table_name="evaluation_regressions")
    op.drop_index("ix_evaluation_regressions_before_evaluation_run_id", table_name="evaluation_regressions")
    op.drop_index("ix_evaluation_regressions_assistant_type", table_name="evaluation_regressions")
    op.drop_index("ix_evaluation_regressions_after_evaluation_run_id", table_name="evaluation_regressions")
    op.drop_table("evaluation_regressions")
    postgresql.ENUM(name="evaluationimprovementregressionstatus").drop(op.get_bind(), checkfirst=True)
