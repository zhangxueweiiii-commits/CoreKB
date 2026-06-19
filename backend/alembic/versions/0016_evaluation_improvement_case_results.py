"""add explicit improvement item case result links

Revision ID: 0016_evaluation_improvement_case_results
Revises: 0015_evaluation_case_annotations
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0016_evaluation_improvement_case_results"
down_revision: str | None = "0015_evaluation_case_annotations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


relation_source_enum = postgresql.ENUM(
    "system_rule",
    "human_annotation",
    "manual_link",
    name="evaluationimprovementrelationsource",
)


def upgrade() -> None:
    relation_source_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "evaluation_improvement_item_case_results",
        sa.Column("improvement_item_id", sa.UUID(), nullable=False),
        sa.Column("evaluation_case_result_id", sa.UUID(), nullable=False),
        sa.Column("relation_source", relation_source_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_case_result_id"],
            ["evaluation_case_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["improvement_item_id"],
            ["evaluation_improvement_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "improvement_item_id",
            "evaluation_case_result_id",
            name="uq_eval_improvement_item_case_result",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_improvement_item_case_results_improvement_item_id"),
        "evaluation_improvement_item_case_results",
        ["improvement_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_improvement_item_case_results_evaluation_case_result_id"),
        "evaluation_improvement_item_case_results",
        ["evaluation_case_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_improvement_item_case_results_relation_source"),
        "evaluation_improvement_item_case_results",
        ["relation_source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_evaluation_improvement_item_case_results_relation_source"),
        table_name="evaluation_improvement_item_case_results",
    )
    op.drop_index(
        op.f("ix_evaluation_improvement_item_case_results_evaluation_case_result_id"),
        table_name="evaluation_improvement_item_case_results",
    )
    op.drop_index(
        op.f("ix_evaluation_improvement_item_case_results_improvement_item_id"),
        table_name="evaluation_improvement_item_case_results",
    )
    op.drop_table("evaluation_improvement_item_case_results")
    relation_source_enum.drop(op.get_bind(), checkfirst=True)
