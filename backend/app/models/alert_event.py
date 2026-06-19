import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AlertEventStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    ignored = "ignored"


class AlertEvent(Base, UUIDMixin):
    __tablename__ = "alert_events"

    alert_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[AlertEventStatus] = mapped_column(
        Enum(AlertEventStatus), default=AlertEventStatus.open, nullable=False, index=True
    )
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
