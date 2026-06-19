import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentMetadataSuggestion,
    DocumentMetadataSuggestionConfidence,
    DocumentMetadataSuggestionSource,
    DocumentMetadataSuggestionStatus,
    DocumentStatus,
)
from app.models.user import User
from app.services.document_parser import DocumentParser
from app.services.metadata_dictionary_service import MetadataDictionaryService


SUPPORTED_METADATA_FIELDS = {
    "category",
    "doc_type",
    "equipment_model",
    "fault_code",
    "material_code",
    "product_model",
    "process_name",
    "sop_code",
    "version",
    "effective_date",
}


@dataclass(frozen=True)
class MetadataSuggestionCandidate:
    field: str
    raw_value: str
    normalized_value: str
    normalization_source: str
    dictionary_entry_id: UUID | None
    suggested_value: str
    confidence: str
    source: str
    evidence_excerpt: str
    rule_name: str


DOC_TYPE_KEYWORDS = {
    "maintenance": [("维修手册", "维修手册"), ("维修指南", "维修手册"), ("故障代码", "故障代码表")],
    "sop": [("作业指导书", "作业指导书"), ("SOP", "作业指导书"), ("操作规程", "作业指导书")],
    "quality": [("检验规范", "检验规范"), ("质量标准", "质量标准"), ("检验标准", "检验规范")],
    "material": [("物料规格书", "物料规格书"), ("产品参数表", "产品参数表"), ("参数表", "产品参数表"), ("备件清单", "备件清单")],
}


class DocumentMetadataSuggester:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def suggest_document_metadata(self, document: Document) -> list[MetadataSuggestionCandidate]:
        if document.status not in {DocumentStatus.indexed, DocumentStatus.parsed}:
            raise ValueError("Document must be parsed or indexed before generating metadata suggestions")
        sections = DocumentParser().parse(document.file_path)
        title = self._title_from_sections(document, sections)
        text = "\n".join(section.text for section in sections)[:12000]
        candidates = [
            *self.extract_metadata_from_filename(document.filename),
            *self.extract_metadata_from_title(title),
            *self.extract_metadata_from_parsed_text(text),
        ]
        return self._dedupe_candidates(candidates)

    def generate_suggestions(self, document: Document) -> list[DocumentMetadataSuggestion]:
        if self.db is None:
            raise RuntimeError("A database session is required to persist suggestions")
        candidates = self.suggest_document_metadata(document)
        created_or_existing: list[DocumentMetadataSuggestion] = []
        for candidate in candidates:
            existing = self.db.scalar(
                select(DocumentMetadataSuggestion).where(
                    DocumentMetadataSuggestion.document_id == document.id,
                    DocumentMetadataSuggestion.field == candidate.field,
                    DocumentMetadataSuggestion.suggested_value == candidate.suggested_value,
                )
            )
            if existing:
                created_or_existing.append(existing)
                continue
            suggestion = DocumentMetadataSuggestion(
                document_id=document.id,
                field=candidate.field,
                raw_value=candidate.raw_value,
                normalized_value=candidate.normalized_value,
                normalization_source=candidate.normalization_source,
                dictionary_entry_id=candidate.dictionary_entry_id,
                suggested_value=candidate.suggested_value,
                confidence=DocumentMetadataSuggestionConfidence(candidate.confidence),
                source=DocumentMetadataSuggestionSource(candidate.source),
                evidence_excerpt=candidate.evidence_excerpt[:500],
                rule_name=candidate.rule_name,
                status=DocumentMetadataSuggestionStatus.pending,
            )
            self.db.add(suggestion)
            created_or_existing.append(suggestion)
        self.db.commit()
        for suggestion in created_or_existing:
            self.db.refresh(suggestion)
        return created_or_existing

    def accept_suggestion(
        self,
        document: Document,
        suggestion: DocumentMetadataSuggestion,
        user: User,
        value: str | None = None,
        custom_value: bool = False,
    ) -> DocumentMetadataSuggestion:
        raw_value = (value or suggestion.normalized_value or suggestion.suggested_value).strip()
        if custom_value:
            accepted_value = raw_value
            suggestion.custom_value = True
        else:
            normalized = self._normalize(suggestion.field, raw_value)
            accepted_value = normalized.normalized_value
            suggestion.custom_value = False
            suggestion.raw_value = raw_value
            suggestion.normalized_value = normalized.normalized_value
            suggestion.normalization_source = normalized.normalization_source
            suggestion.dictionary_entry_id = normalized.dictionary_entry_id
            suggestion.suggested_value = normalized.normalized_value
        meta = dict(document.meta or {})
        meta[suggestion.field] = accepted_value
        document.meta = meta
        suggestion.status = DocumentMetadataSuggestionStatus.accepted
        suggestion.reviewed_by = user.id
        suggestion.reviewed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def reject_suggestion(self, suggestion: DocumentMetadataSuggestion, user: User) -> DocumentMetadataSuggestion:
        suggestion.status = DocumentMetadataSuggestionStatus.rejected
        suggestion.reviewed_by = user.id
        suggestion.reviewed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def extract_metadata_from_filename(self, filename: str) -> list[MetadataSuggestionCandidate]:
        return self._extract_from_text(Path(filename).stem, DocumentMetadataSuggestionSource.filename.value, "high")

    def extract_metadata_from_title(self, title: str | None) -> list[MetadataSuggestionCandidate]:
        return [] if not title else self._extract_from_text(title, DocumentMetadataSuggestionSource.title.value, "high")

    def extract_metadata_from_parsed_text(self, text: str) -> list[MetadataSuggestionCandidate]:
        return self._extract_from_text(text, DocumentMetadataSuggestionSource.parsed_text.value, "medium")

    def normalize_metadata_value(self, field: str, value: str) -> str:
        if field == "version":
            return value.strip().upper().replace("版本", "").strip()
        return MetadataDictionaryService.rule_normalize_metadata_value(field, value)

    def _extract_from_text(self, text: str, source: str, default_confidence: str) -> list[MetadataSuggestionCandidate]:
        boundary = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
        candidates: list[MetadataSuggestionCandidate] = []
        candidates.extend(self._extract_doc_type(text, source, default_confidence))
        candidates.extend(self._extract_pattern(text, source, default_confidence, "equipment_model", boundary.format(r"(?:EQ-)?[A-Z]-?\d{2,4}"), "model_pattern"))
        candidates.extend(self._extract_fault_code(text, source, default_confidence))
        candidates.extend(self._extract_pattern(text, source, default_confidence, "material_code", boundary.format(r"(?:MAT-\d{3,}|MAT\s+\d{3,}|M\d{3,}|WL-\d{3,})"), "material_code_pattern"))
        candidates.extend(self._extract_pattern(text, source, default_confidence, "sop_code", boundary.format(r"SOP[\s-]?\d{3,}"), "sop_code_pattern"))
        candidates.extend(self._extract_pattern(text, source, "medium", "product_model", boundary.format(r"P[A-Z]?-?\d{2,4}"), "product_model_pattern"))
        candidates.extend(self._extract_pattern(text, source, "medium", "version", boundary.format(r"(?:V\d+(?:\.\d+)?|Rev\.[A-Z]|版本\s*\d+(?:\.\d+)?)"), "version_pattern"))
        candidates.extend(self._extract_pattern(text, source, "low", "effective_date", boundary.format(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?"), "effective_date_pattern"))
        return candidates

    def _extract_doc_type(self, text: str, source: str, confidence: str) -> list[MetadataSuggestionCandidate]:
        candidates: list[MetadataSuggestionCandidate] = []
        for category, keywords in DOC_TYPE_KEYWORDS.items():
            for keyword, doc_type in keywords:
                if keyword in text:
                    excerpt = self._excerpt(text, keyword)
                    candidates.append(self._candidate("category", category, confidence, source, excerpt, "doc_type_keyword"))
                    candidates.append(self._candidate("doc_type", doc_type, confidence, source, excerpt, "doc_type_keyword"))
                    break
        return candidates

    def _extract_pattern(
        self,
        text: str,
        source: str,
        confidence: str,
        field: str,
        pattern: str,
        rule_name: str,
    ) -> list[MetadataSuggestionCandidate]:
        candidates = []
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(0)
            if field in {"equipment_model", "product_model"} and self._looks_like_noise(raw):
                continue
            candidates.append(self._candidate(field, raw, confidence, source, self._excerpt(text, raw), rule_name))
        return candidates

    def _extract_fault_code(self, text: str, source: str, confidence: str) -> list[MetadataSuggestionCandidate]:
        pattern = r"(?:故障码\s*)?(?:E-?\d{1,3}|ERR\s*-?\s*\d{1,3}|Error\s+\d{1,3})"
        return [
            self._candidate("fault_code", match.group(0), confidence, source, self._excerpt(text, match.group(0)), "fault_code_pattern")
            for match in re.finditer(pattern, text, flags=re.IGNORECASE)
        ]

    def _candidate(
        self,
        field: str,
        raw_value: str,
        confidence: str,
        source: str,
        evidence_excerpt: str,
        rule_name: str,
    ) -> MetadataSuggestionCandidate:
        normalized = self._normalize(field, raw_value)
        return MetadataSuggestionCandidate(
            field=field,
            raw_value=raw_value,
            normalized_value=normalized.normalized_value,
            normalization_source=normalized.normalization_source,
            dictionary_entry_id=normalized.dictionary_entry_id,
            suggested_value=normalized.normalized_value,
            confidence=confidence,
            source=source,
            evidence_excerpt=evidence_excerpt,
            rule_name=rule_name,
        )

    def _normalize(self, field: str, raw_value: str):
        if self.db is not None:
            result = MetadataDictionaryService(self.db).normalize_with_dictionary(field, raw_value)
            return _Normalization(result.normalized_value, result.matched_by, result.dictionary_entry_id)
        normalized = self.normalize_metadata_value(field, raw_value)
        source = "rule" if normalized != raw_value.strip() else "fallback"
        return _Normalization(normalized, source, None)

    @staticmethod
    def _title_from_sections(document: Document, sections) -> str | None:
        if (document.meta or {}).get("document_title"):
            return str(document.meta["document_title"])
        for section in sections:
            if section.section_title:
                return section.section_title
        return Path(document.filename).stem

    @staticmethod
    def _dedupe_candidates(candidates: list[MetadataSuggestionCandidate]) -> list[MetadataSuggestionCandidate]:
        seen: set[tuple[str, str]] = set()
        result: list[MetadataSuggestionCandidate] = []
        for candidate in candidates:
            if candidate.field not in SUPPORTED_METADATA_FIELDS:
                continue
            key = (candidate.field, candidate.suggested_value)
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    @staticmethod
    def _excerpt(text: str, needle: str, radius: int = 80) -> str:
        index = text.lower().find(needle.lower())
        if index < 0:
            return text[:160]
        start = max(index - radius, 0)
        end = min(index + len(needle) + radius, len(text))
        return text[start:end].strip()

    @staticmethod
    def _looks_like_noise(value: str) -> bool:
        return bool(re.fullmatch(r"[V]\d{2,4}", value.upper()))


@dataclass(frozen=True)
class _Normalization:
    normalized_value: str
    normalization_source: str
    dictionary_entry_id: UUID | None
