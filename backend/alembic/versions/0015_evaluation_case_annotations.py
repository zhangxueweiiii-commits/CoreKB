"""evaluation case annotations

Revision ID: 0015_evaluation_case_annotations
Revises: 0014_evaluation_case_results
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_evaluation_case_annotations"
down_revision: str | None = "0014_evaluation_case_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


human_judgement_enum = postgresql.ENUM(
    "system_correct",
    "system_partially_correct",
    "system_incorrect",
    "business_expected_answer_wrong",
    "insufficient_documentation",
    "needs_expert_review",
    name="humanjudgement",
    create_type=False,
)
human_root_cause_enum = postgresql.ENUM(
    "prompt",
    "metadata_filter",
    "document_metadata",
    "chunking",
    "rerank",
    "parser",
    "source_document",
    "evaluation_case",
    "business_rule",
    "unknown",
    name="humanrootcause",
    create_type=False,
)
human_fix_type_enum = postgresql.ENUM(
    "update_prompt",
    "update_metadata",
    "update_chunking",
    "tune_rerank",
    "improve_parser",
    "supplement_document",
    "revise_eval_case",
    "confirm_business_rule",
    "no_action",
    name="humanfixtype",
    create_type=False,
)
handling_status_enum = postgresql.ENUM(
    "open",
    "investigating",
    "planned",
    "resolved",
    "ignored",
    name="handlingstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    human_judgement_enum.create(bind, checkfirst=True)
    human_root_cause_enum.create(bind, checkfirst=True)
    human_fix_type_enum.create(bind, checkfirst=True)
    handling_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "evaluation_case_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_case_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("human_judgement", human_judgement_enum, nullable=False),
        sa.Column("human_root_cause", human_root_cause_enum, nullable=False),
        sa.Column("human_fix_type", human_fix_type_enum, nullable=False),
        sa.Column("handling_status", handling_status_enum, nullable=False),
        sa.Column("handling_notes", sa.Text(), nullable=True),
        sa.Column("annotated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("annotated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["annotated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evaluation_case_result_id"], ["evaluation_case_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_case_result_id", name="uq_evaluation_case_annotations_case_result"),
    )
    op.create_index(
        "ix_evaluation_case_annotations_evaluation_case_result_id",
        "evaluation_case_annotations",
        ["evaluation_case_result_id"],
    )
    op.create_index("ix_evaluation_case_annotations_human_judgement", "evaluation_case_annotations", ["human_judgement"])
    op.create_index("ix_evaluation_case_annotations_human_root_cause", "evaluation_case_annotations", ["human_root_cause"])
    op.create_index("ix_evaluation_case_annotations_human_fix_type", "evaluation_case_annotations", ["human_fix_type"])
    op.create_index("ix_evaluation_case_annotations_handling_status", "evaluation_case_annotations", ["handling_status"])

    op.add_column(
        "evaluation_improvement_items",
        sa.Column("source", sa.Text(), server_default="system_rule", nullable=False),
    )
    op.add_column(
        "evaluation_improvement_items",
        sa.Column("annotation_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_evaluation_improvement_items_source", "evaluation_improvement_items", ["source"])
    op.alter_column("evaluation_improvement_items", "source", server_default=None)
    op.alter_column("evaluation_improvement_items", "annotation_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_evaluation_improvement_items_source", table_name="evaluation_improvement_items")
    op.drop_column("evaluation_improvement_items", "annotation_count")
    op.drop_column("evaluation_improvement_items", "source")

    op.drop_index("ix_evaluation_case_annotations_handling_status", table_name="evaluation_case_annotations")
    op.drop_index("ix_evaluation_case_annotations_human_fix_type", table_name="evaluation_case_annotations")
    op.drop_index("ix_evaluation_case_annotations_human_root_cause", table_name="evaluation_case_annotations")
    op.drop_index("ix_evaluation_case_annotations_human_judgement", table_name="evaluation_case_annotations")
    op.drop_index("ix_evaluation_case_annotations_evaluation_case_result_id", table_name="evaluation_case_annotations")
    op.drop_table("evaluation_case_annotations")

    bind = op.get_bind()
    handling_status_enum.drop(bind, checkfirst=True)
    human_fix_type_enum.drop(bind, checkfirst=True)
    human_root_cause_enum.drop(bind, checkfirst=True)
    human_judgement_enum.drop(bind, checkfirst=True)
