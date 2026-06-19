from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.metadata_dictionary_service import MetadataDictionaryService, SUPPORTED_DICTIONARY_FIELDS


PRECHECK_FIELDS = set(SUPPORTED_DICTIONARY_FIELDS)
INVALID_METADATA_VALUES = {"", "-", "--", "n/a", "na", "none", "null", "unknown", "未知", "无", "暂无"}


@dataclass(frozen=True)
class MetadataPrecheckItem:
    document_id: UUID
    document_name: str
    knowledge_base_id: UUID
    field_name: str
    current_value: str
    suggested_value: str | None
    status: str
    matched_by: str
    dictionary_entry_id: UUID | None
    recommended_action: str
    reason: str


class MetadataNormalizationPrecheckService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dictionary = MetadataDictionaryService(db)

    def run_metadata_normalization_precheck(
        self,
        knowledge_base_id: UUID | None = None,
        document_id: UUID | None = None,
        field_name: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "document_id",
        order_direction: str = "asc",
    ) -> dict:
        all_items = self._collect_items(knowledge_base_id=knowledge_base_id, document_id=document_id)
        if field_name:
            all_items = [item for item in all_items if item.field_name == field_name]
        if status:
            all_items = [item for item in all_items if item.status == status]
        all_items = self._sort_items(all_items, order_by=order_by, order_direction=order_direction)
        page = max(page, 1)
        page_size = max(min(page_size, 200), 1)
        start = (page - 1) * page_size
        paged_items = all_items[start:start + page_size]
        summary_source = self._collect_items(knowledge_base_id=knowledge_base_id, document_id=document_id)
        return {
            "summary": self.build_precheck_summary(summary_source),
            "items": [item.__dict__ for item in paged_items],
            "total": len(all_items),
            "page": page,
            "page_size": page_size,
            "pages": (len(all_items) + page_size - 1) // page_size if all_items else 0,
        }

    def get_summary(self, knowledge_base_id: UUID | None = None) -> dict:
        items = self._collect_items(knowledge_base_id=knowledge_base_id)
        by_field_status: dict[str, Counter] = defaultdict(Counter)
        by_status = Counter(item.status for item in items)
        kb_fixable: Counter[str] = Counter()
        dictionary_missing_values: Counter[str] = Counter()
        alias_values: Counter[str] = Counter()
        for item in items:
            by_field_status[item.field_name][item.status] += 1
            if item.recommended_action in {"review_and_normalize", "add_dictionary_entry", "review_invalid_value"}:
                kb_fixable[str(item.knowledge_base_id)] += 1
            if item.status == "dictionary_missing":
                dictionary_missing_values[f"{item.field_name}:{item.current_value}"] += 1
            if item.status == "alias_match":
                alias_values[f"{item.field_name}:{item.current_value}->{item.suggested_value}"] += 1
        return {
            "summary": self.build_precheck_summary(items),
            "by_field": {field: dict(counter) for field, counter in by_field_status.items()},
            "by_status": dict(by_status),
            "top_dictionary_missing_values": [
                {"key": key, "count": count} for key, count in dictionary_missing_values.most_common(10)
            ],
            "top_alias_match_values": [
                {"key": key, "count": count} for key, count in alias_values.most_common(10)
            ],
            "fixable_by_knowledge_base": [
                {"knowledge_base_id": key, "count": count} for key, count in kb_fixable.most_common()
            ],
        }

    def inspect_document_metadata(self, document: Document) -> list[MetadataPrecheckItem]:
        meta = document.meta or {}
        items: list[MetadataPrecheckItem] = []
        for field_name, value in meta.items():
            if field_name not in PRECHECK_FIELDS:
                items.append(
                    MetadataPrecheckItem(
                        document_id=document.id,
                        document_name=document.filename,
                        knowledge_base_id=document.knowledge_base_id,
                        field_name=field_name,
                        current_value=str(value),
                        suggested_value=None,
                        status="unsupported",
                        matched_by="unsupported",
                        dictionary_entry_id=None,
                        recommended_action="ignore",
                        reason="This metadata field is not supported by the first precheck version.",
                    )
                )
                continue
            items.append(self.inspect_metadata_field(document, field_name, value))
        return items

    def inspect_metadata_field(self, document: Document, field_name: str, raw_value) -> MetadataPrecheckItem:
        current_value = "" if raw_value is None else str(raw_value).strip()
        status, suggested_value, matched_by, dictionary_entry_id, reason = self.classify_normalization_result(
            field_name,
            current_value,
        )
        return MetadataPrecheckItem(
            document_id=document.id,
            document_name=document.filename,
            knowledge_base_id=document.knowledge_base_id,
            field_name=field_name,
            current_value=current_value,
            suggested_value=suggested_value,
            status=status,
            matched_by=matched_by,
            dictionary_entry_id=dictionary_entry_id,
            recommended_action=self.build_recommended_action(status),
            reason=reason,
        )

    def classify_normalization_result(
        self,
        field_name: str,
        current_value: str,
    ) -> tuple[str, str | None, str, UUID | None, str]:
        if field_name not in PRECHECK_FIELDS:
            return "unsupported", None, "unsupported", None, "This metadata field is not supported."
        if self._invalid_or_empty(current_value):
            return "invalid_or_empty", None, "invalid", None, "Value is empty, invalid, or a known placeholder."
        dictionary_match = self.dictionary.find_dictionary_match(field_name, current_value)
        if dictionary_match:
            if self._same(dictionary_match.canonical_value, current_value):
                return (
                    "canonical",
                    dictionary_match.canonical_value,
                    "dictionary_canonical",
                    dictionary_match.id,
                    "Current value is an active dictionary canonical value.",
                )
            return (
                "alias_match",
                dictionary_match.canonical_value,
                "dictionary_alias",
                dictionary_match.id,
                f"Current value matches dictionary alias {current_value}.",
            )
        rule_value = self.dictionary.rule_normalize_metadata_value(field_name, current_value)
        if rule_value and not self._same(rule_value, current_value):
            if not self.dictionary.find_dictionary_match(field_name, rule_value):
                return (
                    "rule_normalizable",
                    rule_value,
                    "rule",
                    None,
                    "Current value can be normalized by existing rules but has no active dictionary match.",
                )
        return (
            "dictionary_missing",
            current_value,
            "fallback",
            None,
            "Value is present but no active dictionary canonical or alias matched it.",
        )

    @staticmethod
    def build_precheck_summary(items: list[MetadataPrecheckItem]) -> dict:
        document_ids = {item.document_id for item in items}
        counter = Counter(item.status for item in items)
        return {
            "documents_scanned": len(document_ids),
            "metadata_fields_scanned": len(items),
            "canonical_count": counter.get("canonical", 0),
            "alias_match_count": counter.get("alias_match", 0),
            "rule_normalizable_count": counter.get("rule_normalizable", 0),
            "dictionary_missing_count": counter.get("dictionary_missing", 0),
            "invalid_or_empty_count": counter.get("invalid_or_empty", 0),
            "unsupported_count": counter.get("unsupported", 0),
        }

    @staticmethod
    def build_recommended_action(status: str) -> str:
        return {
            "canonical": "no_action",
            "alias_match": "review_and_normalize",
            "rule_normalizable": "review_and_normalize",
            "dictionary_missing": "add_dictionary_entry",
            "invalid_or_empty": "review_invalid_value",
            "unsupported": "ignore",
        }.get(status, "ignore")

    def _collect_items(self, knowledge_base_id: UUID | None = None, document_id: UUID | None = None) -> list[MetadataPrecheckItem]:
        stmt = select(Document).order_by(Document.id.asc())
        if knowledge_base_id:
            stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
        if document_id:
            stmt = stmt.where(Document.id == document_id)
        documents = list(self.db.scalars(stmt).all())
        items: list[MetadataPrecheckItem] = []
        for document in documents:
            items.extend(self.inspect_document_metadata(document))
        return items

    @staticmethod
    def _sort_items(items: list[MetadataPrecheckItem], order_by: str, order_direction: str) -> list[MetadataPrecheckItem]:
        allowed = {"document_id", "document_name", "field_name", "status", "current_value"}
        if order_by not in allowed:
            raise ValueError(f"Invalid order_by: {order_by}")
        if order_direction not in {"asc", "desc"}:
            raise ValueError(f"Invalid order_direction: {order_direction}")
        reverse = order_direction == "desc"
        return sorted(items, key=lambda item: str(getattr(item, order_by)), reverse=reverse)

    @staticmethod
    def _invalid_or_empty(value: str) -> bool:
        return (value or "").strip().casefold() in INVALID_METADATA_VALUES

    @staticmethod
    def _same(left: str, right: str) -> bool:
        return (left or "").strip().casefold() == (right or "").strip().casefold()
