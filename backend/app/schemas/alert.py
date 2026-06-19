from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.alert_event import AlertEventStatus


class AlertEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_type: str
    severity: str
    title: str
    message: str
    resource_type: str | None = None
    resource_id: str | None = None
    status: AlertEventStatus
    webhook_sent: bool
    webhook_error: str | None = None
    metadata: dict = Field(default_factory=dict, validation_alias="meta", serialization_alias="metadata")
    created_at: datetime
    resolved_at: datetime | None = None
