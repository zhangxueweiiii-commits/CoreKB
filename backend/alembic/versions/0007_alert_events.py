"""alert events

Revision ID: 0007_alert_events
Revises: 0006_backup_jobs
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_alert_events"
down_revision: str | None = "0006_backup_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


alert_event_status = postgresql.ENUM("open", "resolved", "ignored", name="alerteventstatus", create_type=False)


def upgrade() -> None:
    alert_event_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("status", alert_event_status, nullable=False),
        sa.Column("webhook_sent", sa.Boolean(), nullable=False),
        sa.Column("webhook_error", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_events_alert_type", "alert_events", ["alert_type"])
    op.create_index("ix_alert_events_severity", "alert_events", ["severity"])
    op.create_index("ix_alert_events_status", "alert_events", ["status"])
    op.create_index("ix_alert_events_resource_type", "alert_events", ["resource_type"])
    op.create_index("ix_alert_events_resource_id", "alert_events", ["resource_id"])
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_alert_events_created_at", table_name="alert_events")
    op.drop_index("ix_alert_events_resource_id", table_name="alert_events")
    op.drop_index("ix_alert_events_resource_type", table_name="alert_events")
    op.drop_index("ix_alert_events_status", table_name="alert_events")
    op.drop_index("ix_alert_events_severity", table_name="alert_events")
    op.drop_index("ix_alert_events_alert_type", table_name="alert_events")
    op.drop_table("alert_events")
    alert_event_status.drop(op.get_bind(), checkfirst=True)
