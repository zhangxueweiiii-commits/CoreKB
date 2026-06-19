from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentMetadataSuggestion,
    DocumentMetadataSuggestionConfidence,
    DocumentMetadataSuggestionSource,
    DocumentMetadataSuggestionStatus,
)
from app.models.validation_report import ValidationReport, ValidationReportType
from app.services.document_metadata_suggester import DocumentMetadataSuggester, SUPPORTED_METADATA_FIELDS
from app.services.metadata_dictionary_service import MetadataDictionaryService, SUPPORTED_DICTIONARY_FIELDS


FIELD_ALIASES = {
    "document_type": "doc_type",
}


@dataclass
class SkippedValidationIssue:
    field: str | None
    code: str | None
    reason: str


@dataclass
class ValidationReportSuggestionBridgeResult:
    created: list[DocumentMetadataSuggestion] = field(default_factory=list)
    existing: list[DocumentMetadataSuggestion] = field(default_factory=list)
    skipped: list[SkippedValidationIssue] = field(default_factory=list)

    @property
    def items(self) -> list[DocumentMetadataSuggestion]:
        return [*self.created, *self.existing]


class ValidationReportSuggestionBridge:
    """Creates pending metadata suggestions from validation report issues.

    This service intentionally stops at the review boundary: it never writes
    formal document metadata, accepts suggestions, or triggers reindexing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_pending_suggestions(
        self,
        *,
        report: ValidationReport,
        document: Document,
    ) -> ValidationReportSuggestionBridgeResult:
        if report.report_type != ValidationReportType.metadata:
            raise ValueError("Only metadata validation reports can create metadata suggestions")
        result = ValidationReportSuggestionBridgeResult()
        for issue in report.issues_json or []:
            self._create_from_issue(report, document, issue, result)
        self.db.commit()
        for suggestion in result.items:
            self.db.refresh(suggestion)
        return result

    def _create_from_issue(
        self,
        report: ValidationReport,
        document: Document,
        issue: dict[str, Any],
        result: ValidationReportSuggestionBridgeResult,
    ) -> None:
        raw_field = self._string(issue.get("field"))
        field_name = self._normalize_field_name(raw_field)
        code = self._string(issue.get("code"))
        if not field_name or field_name not in SUPPORTED_METADATA_FIELDS:
            result.skipped.append(SkippedValidationIssue(raw_field, code, "unsupported_metadata_field"))
            return
        raw_value = self._string(issue.get("current_value"))
        if not raw_value:
            result.skipped.append(SkippedValidationIssue(field_name, code, "missing_current_value"))
            return
        normalized = self._normalize(field_name, raw_value)
        if not normalized["suggested_value"]:
            result.skipped.append(SkippedValidationIssue(field_name, code, "empty_normalized_value"))
            return
        existing = self.db.scalar(
            select(DocumentMetadataSuggestion).where(
                DocumentMetadataSuggestion.document_id == document.id,
                DocumentMetadataSuggestion.field == field_name,
                DocumentMetadataSuggestion.suggested_value == normalized["suggested_value"],
            )
        )
        if existing:
            result.existing.append(existing)
            return
        suggestion = DocumentMetadataSuggestion(
            document_id=document.id,
            field=field_name,
            raw_value=raw_value,
            normalized_value=normalized["suggested_value"],
            normalization_source=normalized["normalization_source"],
            dictionary_entry_id=normalized["dictionary_entry_id"],
            suggested_value=normalized["suggested_value"],
            confidence=DocumentMetadataSuggestionConfidence.medium
            if normalized["normalization_source"] in {"canonical", "alias", "rule"}
            else DocumentMetadataSuggestionConfidence.low,
            source=DocumentMetadataSuggestionSource.parsed_text,
            evidence_excerpt=self._evidence_excerpt(report, issue),
            rule_name="validation_report_bridge",
            status=DocumentMetadataSuggestionStatus.pending,
        )
        self.db.add(suggestion)
        result.created.append(suggestion)

    def _normalize(self, field_name: str, raw_value: str) -> dict[str, Any]:
        if field_name in SUPPORTED_DICTIONARY_FIELDS:
            result = MetadataDictionaryService(self.db).normalize_with_dictionary(field_name, raw_value)
            return {
                "suggested_value": result.normalized_value,
                "normalization_source": result.matched_by,
                "dictionary_entry_id": result.dictionary_entry_id,
            }
        normalized = DocumentMetadataSuggester(self.db).normalize_metadata_value(field_name, raw_value)
        return {
            "suggested_value": normalized,
            "normalization_source": "rule" if normalized != raw_value.strip() else "fallback",
            "dictionary_entry_id": None,
        }

    @staticmethod
    def _normalize_field_name(field_name: str | None) -> str | None:
        if not field_name:
            return None
        return FIELD_ALIASES.get(field_name, field_name)

    @staticmethod
    def _evidence_excerpt(report: ValidationReport, issue: dict[str, Any]) -> str:
        message = str(issue.get("message") or issue.get("code") or "Validation report issue").strip()
        return f"Validation report {report.id}: {message}"[:500]

    @staticmethod
    def _string(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return str(value).strip() or None
