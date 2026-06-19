from uuid import UUID

from pydantic import BaseModel, Field


class MetadataPrecheckSummary(BaseModel):
    documents_scanned: int
    metadata_fields_scanned: int
    canonical_count: int
    alias_match_count: int
    rule_normalizable_count: int
    dictionary_missing_count: int
    invalid_or_empty_count: int
    unsupported_count: int = 0


class MetadataPrecheckItem(BaseModel):
    document_id: UUID
    document_name: str
    knowledge_base_id: UUID
    field_name: str
    current_value: str
    suggested_value: str | None = None
    status: str
    matched_by: str
    dictionary_entry_id: UUID | None = None
    recommended_action: str
    reason: str


class MetadataPrecheckResponse(BaseModel):
    summary: MetadataPrecheckSummary
    items: list[MetadataPrecheckItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class MetadataPrecheckTopValue(BaseModel):
    key: str
    count: int


class MetadataPrecheckKbCount(BaseModel):
    knowledge_base_id: str
    count: int


class MetadataPrecheckSummaryResponse(BaseModel):
    summary: MetadataPrecheckSummary
    by_field: dict[str, dict[str, int]]
    by_status: dict[str, int]
    top_dictionary_missing_values: list[MetadataPrecheckTopValue] = Field(default_factory=list)
    top_alias_match_values: list[MetadataPrecheckTopValue] = Field(default_factory=list)
    fixable_by_knowledge_base: list[MetadataPrecheckKbCount] = Field(default_factory=list)
