from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceRecordDraftCreate(BaseModel):
    equipment_model: str | None = None
    fault_symptom: str
    fault_code: str | None = None
    assistant_answer_snapshot: str
    selected_evidence_snapshot: list[dict] = Field(default_factory=list)
    citation_metadata: list[dict] = Field(default_factory=list)
    metadata_filter_used: dict = Field(default_factory=dict)
    rerank_state: dict = Field(default_factory=dict)
    draft_text: str


class MaintenanceRecordDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    equipment_model: str | None = None
    fault_symptom: str
    fault_code: str | None = None
    assistant_answer_snapshot: str
    selected_evidence_snapshot: list[dict]
    citation_metadata: list[dict]
    metadata_filter_used: dict
    rerank_state: dict
    draft_text: str
    status: str
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class MaintenanceExperienceCandidateCreate(BaseModel):
    title: str
    equipment_model: str | None = None
    fault_code: str | None = None
    fault_symptom: str
    root_cause_candidate: str | None = None
    effective_handling_method: str
    ineffective_handling_method: str | None = None
    spare_parts_involved: str | None = None
    safety_notes: str | None = None
    applicable_scope: str | None = None
    evidence_references: list[dict] = Field(default_factory=list)
    source_record_draft_id: UUID | None = None


class MaintenanceCandidateReviewRequest(BaseModel):
    reviewer_note: str | None = None


class MaintenanceExperienceCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    equipment_model: str | None = None
    fault_code: str | None = None
    fault_symptom: str
    root_cause_candidate: str | None = None
    effective_handling_method: str
    ineffective_handling_method: str | None = None
    spare_parts_involved: str | None = None
    safety_notes: str | None = None
    applicable_scope: str | None = None
    evidence_references: list[dict]
    source_record_draft_id: UUID | None = None
    status: str
    reviewer_note: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class MaintenanceKnowledgeEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    equipment_model: str | None = None
    fault_code: str | None = None
    fault_symptom: str
    root_cause: str | None = None
    solution: str
    spare_parts: str | None = None
    evidence_references: list[dict]
    source_candidate_id: UUID
    status: str
    created_by: UUID | None = None
    accepted_by: UUID | None = None
    accepted_at: datetime
    created_at: datetime
    updated_at: datetime


class MaintenanceCandidateAcceptResponse(BaseModel):
    candidate: MaintenanceExperienceCandidateRead
    knowledge_entry: MaintenanceKnowledgeEntryRead
