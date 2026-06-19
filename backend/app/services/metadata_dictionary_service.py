from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metadata_dictionary import MetadataDictionaryEntry, MetadataDictionaryEntryStatus
from app.models.user import User


SUPPORTED_DICTIONARY_FIELDS = {
    "equipment_model",
    "fault_code",
    "material_code",
    "product_model",
    "sop_code",
    "process_name",
    "doc_type",
    "category",
}


@dataclass(frozen=True)
class MetadataNormalizationResult:
    raw_value: str
    normalized_value: str
    matched_by: str
    dictionary_entry_id: UUID | None = None


class MetadataDictionaryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def normalize_with_dictionary(self, field_name: str, raw_value: str) -> MetadataNormalizationResult:
        if field_name not in SUPPORTED_DICTIONARY_FIELDS:
            return MetadataNormalizationResult(raw_value=raw_value, normalized_value=raw_value, matched_by="fallback")
        match = self.find_dictionary_match(field_name, raw_value)
        if match:
            matched_by = "canonical" if self._same(match.canonical_value, raw_value) else "alias"
            return MetadataNormalizationResult(
                raw_value=raw_value,
                normalized_value=match.canonical_value,
                matched_by=matched_by,
                dictionary_entry_id=match.id,
            )
        normalized = self.rule_normalize_metadata_value(field_name, raw_value)
        if normalized != raw_value.strip():
            return MetadataNormalizationResult(raw_value=raw_value, normalized_value=normalized, matched_by="rule")
        return MetadataNormalizationResult(raw_value=raw_value, normalized_value=raw_value.strip(), matched_by="fallback")

    def find_dictionary_match(self, field_name: str, raw_value: str) -> MetadataDictionaryEntry | None:
        value_key = self._key(raw_value)
        if not value_key:
            return None
        entries = self.db.scalars(
            select(MetadataDictionaryEntry).where(
                MetadataDictionaryEntry.field_name == field_name,
                MetadataDictionaryEntry.status == MetadataDictionaryEntryStatus.active,
            )
        ).all()
        for entry in entries:
            if self._key(entry.canonical_value) == value_key:
                return entry
        for entry in entries:
            if any(self._key(alias) == value_key for alias in (entry.aliases or [])):
                return entry
        return None

    def create_dictionary_entry(
        self,
        field_name: str,
        canonical_value: str,
        aliases: list[str],
        user: User,
        description: str | None = None,
        status: str = "active",
    ) -> MetadataDictionaryEntry:
        self._validate_field(field_name)
        canonical = self.rule_normalize_metadata_value(field_name, canonical_value)
        cleaned_aliases = self._clean_aliases(aliases)
        self.validate_alias_conflicts(field_name, canonical, cleaned_aliases)
        entry = MetadataDictionaryEntry(
            field_name=field_name,
            canonical_value=canonical,
            aliases=cleaned_aliases,
            status=MetadataDictionaryEntryStatus(status),
            description=description,
            created_by=user.id,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def update_dictionary_entry(
        self,
        entry_id: UUID,
        canonical_value: str | None = None,
        aliases: list[str] | None = None,
        status: str | None = None,
        description: str | None = None,
    ) -> MetadataDictionaryEntry:
        entry = self.db.get(MetadataDictionaryEntry, entry_id)
        if not entry:
            raise KeyError("Metadata dictionary entry not found")
        next_canonical = (
            self.rule_normalize_metadata_value(entry.field_name, canonical_value)
            if canonical_value is not None
            else entry.canonical_value
        )
        next_aliases = self._clean_aliases(aliases) if aliases is not None else list(entry.aliases or [])
        if status is not None:
            entry.status = MetadataDictionaryEntryStatus(status)
        self.validate_alias_conflicts(entry.field_name, next_canonical, next_aliases, exclude_entry_id=entry.id)
        entry.canonical_value = next_canonical
        entry.aliases = next_aliases
        if description is not None:
            entry.description = description
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def add_alias(self, entry_id: UUID, alias: str) -> MetadataDictionaryEntry:
        entry = self.db.get(MetadataDictionaryEntry, entry_id)
        if not entry:
            raise KeyError("Metadata dictionary entry not found")
        aliases = self._clean_aliases([*(entry.aliases or []), alias])
        self.validate_alias_conflicts(entry.field_name, entry.canonical_value, aliases, exclude_entry_id=entry.id)
        entry.aliases = aliases
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def remove_alias(self, entry_id: UUID, alias: str) -> MetadataDictionaryEntry:
        entry = self.db.get(MetadataDictionaryEntry, entry_id)
        if not entry:
            raise KeyError("Metadata dictionary entry not found")
        alias_key = self._key(alias)
        entry.aliases = [item for item in (entry.aliases or []) if self._key(item) != alias_key]
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_entries(
        self,
        field_name: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> list[MetadataDictionaryEntry]:
        stmt = select(MetadataDictionaryEntry).order_by(
            MetadataDictionaryEntry.field_name.asc(),
            MetadataDictionaryEntry.canonical_value.asc(),
        )
        if field_name:
            stmt = stmt.where(MetadataDictionaryEntry.field_name == field_name)
        if status:
            stmt = stmt.where(MetadataDictionaryEntry.status == MetadataDictionaryEntryStatus(status))
        entries = list(self.db.scalars(stmt).all())
        if keyword and keyword.strip():
            key = self._key(keyword)
            entries = [
                entry
                for entry in entries
                if key in self._key(entry.canonical_value)
                or key in self._key(entry.description or "")
                or any(key in self._key(alias) for alias in (entry.aliases or []))
            ]
        return entries

    def validate_alias_conflicts(
        self,
        field_name: str,
        canonical_value: str,
        aliases: list[str],
        exclude_entry_id: UUID | None = None,
    ) -> None:
        self._validate_field(field_name)
        keys = [self._key(alias) for alias in aliases if self._key(alias)]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate aliases are not allowed in one dictionary entry")
        candidate_keys = set(keys)
        candidate_keys.add(self._key(canonical_value))
        stmt = select(MetadataDictionaryEntry).where(
            MetadataDictionaryEntry.field_name == field_name,
            MetadataDictionaryEntry.status == MetadataDictionaryEntryStatus.active,
        )
        if exclude_entry_id:
            stmt = stmt.where(MetadataDictionaryEntry.id != exclude_entry_id)
        for entry in self.db.scalars(stmt).all():
            entry_keys = {self._key(entry.canonical_value), *(self._key(alias) for alias in (entry.aliases or []))}
            overlap = candidate_keys & {key for key in entry_keys if key}
            if overlap:
                raise ValueError("Alias or canonical value conflicts with another active dictionary entry")

    @staticmethod
    def rule_normalize_metadata_value(field_name: str, raw_value: str) -> str:
        import re

        value = (raw_value or "").strip()
        if not value:
            return value
        upper = value.upper()
        if field_name in {"equipment_model", "product_model"}:
            if re.fullmatch(r"[A-Z]-\d{2,4}", upper):
                return upper.replace("-", "")
            return upper
        if field_name == "fault_code":
            normalized = upper.replace("ERR", "E").replace("ERROR", "E")
            digits = re.search(r"\d{1,3}", normalized)
            return f"E{digits.group(0)}" if digits else normalized.replace("-", "")
        if field_name == "material_code":
            return upper.replace("物料", "").replace(" ", "").strip()
        if field_name == "sop_code":
            digits = re.search(r"SOP[\s-]?(\d{3,})", upper)
            return f"SOP-{digits.group(1)}" if digits else upper
        return value.strip()

    @staticmethod
    def _clean_aliases(aliases: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for alias in aliases or []:
            cleaned = alias.strip()
            if not cleaned:
                continue
            key = MetadataDictionaryService._key(cleaned)
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    @staticmethod
    def _validate_field(field_name: str) -> None:
        if field_name not in SUPPORTED_DICTIONARY_FIELDS:
            raise ValueError(f"Unsupported metadata dictionary field: {field_name}")

    @staticmethod
    def _same(left: str, right: str) -> bool:
        return MetadataDictionaryService._key(left) == MetadataDictionaryService._key(right)

    @staticmethod
    def _key(value: str) -> str:
        return (value or "").strip().casefold()
