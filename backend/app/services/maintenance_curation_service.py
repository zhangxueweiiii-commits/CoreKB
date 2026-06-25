from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maintenance import (
    MaintenanceExperienceCandidate,
    MaintenanceExperienceCandidateStatus,
    MaintenanceKnowledgeEntry,
    MaintenanceKnowledgeEntryStatus,
    MaintenanceRecordDraft,
    MaintenanceRecordDraftStatus,
)
from app.models.user import User
from app.schemas.maintenance import MaintenanceExperienceCandidateCreate, MaintenanceRecordDraftCreate
from app.services.audit_service import AuditService


class MaintenanceCurationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_record_draft(self, payload: MaintenanceRecordDraftCreate, actor: User) -> MaintenanceRecordDraft:
        draft = MaintenanceRecordDraft(
            equipment_model=_clean(payload.equipment_model),
            fault_symptom=payload.fault_symptom,
            fault_code=_clean(payload.fault_code),
            assistant_answer_snapshot=payload.assistant_answer_snapshot,
            selected_evidence_snapshot=payload.selected_evidence_snapshot,
            citation_metadata=payload.citation_metadata,
            metadata_filter_used=payload.metadata_filter_used,
            rerank_state=payload.rerank_state,
            draft_text=payload.draft_text,
            status=MaintenanceRecordDraftStatus.draft,
            created_by=actor.id,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        AuditService(self.db).record(
            actor=actor,
            action="maintenance.record_draft.create",
            resource_type="maintenance_record_draft",
            resource_id=draft.id,
            status="success",
            metadata={
                "equipment_model": draft.equipment_model,
                "fault_code": draft.fault_code,
                "evidence_count": len(draft.selected_evidence_snapshot or []),
                "citation_count": len(draft.citation_metadata or []),
            },
        )
        return draft

    def create_candidate(self, payload: MaintenanceExperienceCandidateCreate, actor: User) -> MaintenanceExperienceCandidate:
        if payload.source_record_draft_id and not self.db.get(MaintenanceRecordDraft, payload.source_record_draft_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance record draft not found")
        candidate = MaintenanceExperienceCandidate(
            title=payload.title,
            equipment_model=_clean(payload.equipment_model),
            fault_code=_clean(payload.fault_code),
            fault_symptom=payload.fault_symptom,
            root_cause_candidate=payload.root_cause_candidate,
            effective_handling_method=payload.effective_handling_method,
            ineffective_handling_method=payload.ineffective_handling_method,
            spare_parts_involved=payload.spare_parts_involved,
            safety_notes=payload.safety_notes,
            applicable_scope=payload.applicable_scope,
            evidence_references=payload.evidence_references,
            source_record_draft_id=payload.source_record_draft_id,
            status=MaintenanceExperienceCandidateStatus.pending,
            created_by=actor.id,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        AuditService(self.db).record(
            actor=actor,
            action="maintenance.experience_candidate.create",
            resource_type="maintenance_experience_candidate",
            resource_id=candidate.id,
            status="success",
            metadata={
                "title": candidate.title,
                "equipment_model": candidate.equipment_model,
                "fault_code": candidate.fault_code,
                "source_record_draft_id": str(candidate.source_record_draft_id) if candidate.source_record_draft_id else None,
                "evidence_count": len(candidate.evidence_references or []),
            },
        )
        return candidate

    def list_candidates(self, status_filter: str | None = None) -> list[MaintenanceExperienceCandidate]:
        stmt = select(MaintenanceExperienceCandidate).order_by(MaintenanceExperienceCandidate.created_at.desc())
        if status_filter:
            stmt = stmt.where(MaintenanceExperienceCandidate.status == MaintenanceExperienceCandidateStatus(status_filter))
        return list(self.db.scalars(stmt).all())

    def accept_candidate(self, candidate_id: UUID, actor: User, reviewer_note: str | None = None) -> tuple[MaintenanceExperienceCandidate, MaintenanceKnowledgeEntry]:
        candidate = self._candidate_or_404(candidate_id)
        if candidate.status != MaintenanceExperienceCandidateStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending candidates can be accepted")
        now = datetime.now(UTC)
        candidate.status = MaintenanceExperienceCandidateStatus.accepted
        candidate.reviewer_note = reviewer_note
        candidate.reviewed_by = actor.id
        candidate.reviewed_at = now
        entry = MaintenanceKnowledgeEntry(
            title=candidate.title,
            equipment_model=candidate.equipment_model,
            fault_code=candidate.fault_code,
            fault_symptom=candidate.fault_symptom,
            root_cause=candidate.root_cause_candidate,
            solution=candidate.effective_handling_method,
            spare_parts=candidate.spare_parts_involved,
            evidence_references=candidate.evidence_references,
            source_candidate_id=candidate.id,
            status=MaintenanceKnowledgeEntryStatus.active,
            created_by=candidate.created_by,
            accepted_by=actor.id,
            accepted_at=now,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(candidate)
        self.db.refresh(entry)
        AuditService(self.db).record(
            actor=actor,
            action="maintenance.experience_candidate.accept",
            resource_type="maintenance_experience_candidate",
            resource_id=candidate.id,
            status="success",
            metadata={"reviewer_note_present": bool(reviewer_note)},
        )
        AuditService(self.db).record(
            actor=actor,
            action="maintenance.knowledge_entry.create",
            resource_type="maintenance_knowledge_entry",
            resource_id=entry.id,
            status="success",
            metadata={
                "source_candidate_id": str(candidate.id),
                "equipment_model": entry.equipment_model,
                "fault_code": entry.fault_code,
            },
        )
        return candidate, entry

    def reject_candidate(self, candidate_id: UUID, actor: User, reviewer_note: str | None = None) -> MaintenanceExperienceCandidate:
        candidate = self._candidate_or_404(candidate_id)
        if candidate.status != MaintenanceExperienceCandidateStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending candidates can be rejected")
        candidate.status = MaintenanceExperienceCandidateStatus.rejected
        candidate.reviewer_note = reviewer_note
        candidate.reviewed_by = actor.id
        candidate.reviewed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(candidate)
        AuditService(self.db).record(
            actor=actor,
            action="maintenance.experience_candidate.reject",
            resource_type="maintenance_experience_candidate",
            resource_id=candidate.id,
            status="success",
            metadata={"reviewer_note_present": bool(reviewer_note)},
        )
        return candidate

    def _candidate_or_404(self, candidate_id: UUID) -> MaintenanceExperienceCandidate:
        candidate = self.db.get(MaintenanceExperienceCandidate, candidate_id)
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance experience candidate not found")
        return candidate


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
