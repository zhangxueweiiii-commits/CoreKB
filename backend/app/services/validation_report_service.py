from __future__ import annotations

import uuid
from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metadata import ValidationIssue
from app.models.validation_report import (
    ValidationReport,
    ValidationReportSeverity,
    ValidationReportStatus,
    ValidationReportType,
)


SEVERITY_RANK = {
    "info": 0,
    "warning": 1,
    "error": 2,
}


def create_validation_report(
    db: Session,
    *,
    document_id: str | uuid.UUID,
    report_type: str = ValidationReportType.metadata.value,
    issues: list[ValidationIssue],
    summary: str | None = None,
) -> ValidationReport:
    serialized_issues = [_serialize_issue(issue) for issue in issues]
    severity = _highest_severity(serialized_issues)
    report = ValidationReport(
        document_id=uuid.UUID(str(document_id)),
        report_type=ValidationReportType(report_type),
        severity=ValidationReportSeverity(severity),
        issue_count=len(serialized_issues),
        issues_json=serialized_issues,
        summary=summary,
        status=ValidationReportStatus.open,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_validation_report(db: Session, report_id: str | uuid.UUID) -> ValidationReport | None:
    return db.get(ValidationReport, uuid.UUID(str(report_id)))


def list_validation_reports_by_document(db: Session, document_id: str | uuid.UUID) -> list[ValidationReport]:
    statement = (
        select(ValidationReport)
        .where(ValidationReport.document_id == uuid.UUID(str(document_id)))
        .order_by(ValidationReport.created_at.desc(), ValidationReport.id.desc())
    )
    return list(db.scalars(statement).all())


def _serialize_issue(issue: ValidationIssue | dict[str, Any]) -> dict[str, Any]:
    if is_dataclass(issue):
        return asdict(issue)
    return dict(issue)


def _highest_severity(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "info"
    return max((str(issue.get("severity", "info")) for issue in issues), key=lambda value: SEVERITY_RANK.get(value, 0))
