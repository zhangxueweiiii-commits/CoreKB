from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ValidationIssueRead(BaseModel):
    field: str
    code: str
    severity: str
    message: str
    current_value: object | None = None
    expected: object | None = None


class ValidationReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    report_type: str
    severity: str
    issue_count: int
    issues_json: list[dict]
    summary: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
