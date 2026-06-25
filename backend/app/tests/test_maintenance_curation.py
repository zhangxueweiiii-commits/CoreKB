from pathlib import Path

from app.models.audit_log import AuditLog
from app.models.document import Document, DocumentStatus
from app.models.index_job import IndexJob
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.maintenance import (
    MaintenanceExperienceCandidate,
    MaintenanceExperienceCandidateStatus,
    MaintenanceKnowledgeEntry,
    MaintenanceRecordDraftStatus,
)
from app.models.user import User, UserRole
from app.schemas.maintenance import MaintenanceExperienceCandidateCreate, MaintenanceRecordDraftCreate
from app.services.maintenance_curation_service import MaintenanceCurationService


def make_user(db, username: str, role: UserRole = UserRole.editor) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_source_document(db, owner: User, tmp_path: Path) -> Document:
    kb = KnowledgeBase(
        name="Maintenance KB",
        description="maintenance",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    path = tmp_path / "A200.txt"
    path.write_text("A200 E12 maintenance manual", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename="A200.txt",
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta={"equipment_model": "A200", "fault_code": "E12"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def record_payload() -> MaintenanceRecordDraftCreate:
    return MaintenanceRecordDraftCreate(
        equipment_model="A200",
        fault_code="E12",
        fault_symptom="Temperature sensor alarm",
        assistant_answer_snapshot="Check wiring and sensor.",
        selected_evidence_snapshot=[{"chunk_id": "chunk-1", "document_id": "doc-1"}],
        citation_metadata=[{"filename": "A200.txt", "chunk_id": "chunk-1"}],
        metadata_filter_used={"category": "maintenance", "equipment_model": "A200"},
        rerank_state={"use_rerank": True, "rerank_applied": True},
        draft_text="Maintenance Record Draft",
    )


def candidate_payload(source_record_draft_id=None) -> MaintenanceExperienceCandidateCreate:
    return MaintenanceExperienceCandidateCreate(
        title="A200 E12 handling",
        equipment_model="A200",
        fault_code="E12",
        fault_symptom="Temperature sensor alarm",
        root_cause_candidate="Sensor wiring abnormal",
        effective_handling_method="Check wiring, replace sensor if needed.",
        ineffective_handling_method="Repeated reset without inspection",
        spare_parts_involved="Temperature sensor",
        safety_notes="Power down before wiring inspection.",
        applicable_scope="A200 with E12",
        evidence_references=[{"chunk_id": "chunk-1", "filename": "A200.txt"}],
        source_record_draft_id=source_record_draft_id,
    )


def test_saving_maintenance_record_draft(db_session):
    user = make_user(db_session, "maintenance-draft-user")
    draft = MaintenanceCurationService(db_session).create_record_draft(record_payload(), user)

    assert draft.status == MaintenanceRecordDraftStatus.draft
    assert draft.created_by == user.id
    assert draft.metadata_filter_used["equipment_model"] == "A200"
    assert db_session.query(AuditLog).filter_by(action="maintenance.record_draft.create").count() == 1


def test_saving_experience_candidate_starts_pending(db_session):
    user = make_user(db_session, "maintenance-candidate-user")
    candidate = MaintenanceCurationService(db_session).create_candidate(candidate_payload(), user)

    assert candidate.status == MaintenanceExperienceCandidateStatus.pending
    assert candidate.created_by == user.id
    assert db_session.query(AuditLog).filter_by(action="maintenance.experience_candidate.create").count() == 1


def test_accepting_candidate_creates_knowledge_entry_and_audit(db_session):
    user = make_user(db_session, "maintenance-accept-user")
    service = MaintenanceCurationService(db_session)
    candidate = service.create_candidate(candidate_payload(), user)

    accepted, entry = service.accept_candidate(candidate.id, user, "Approved after source review")

    assert accepted.status == MaintenanceExperienceCandidateStatus.accepted
    assert accepted.reviewed_by == user.id
    assert entry.source_candidate_id == candidate.id
    assert entry.status.value == "active"
    assert db_session.query(MaintenanceKnowledgeEntry).count() == 1
    assert db_session.query(AuditLog).filter_by(action="maintenance.experience_candidate.accept").count() == 1
    assert db_session.query(AuditLog).filter_by(action="maintenance.knowledge_entry.create").count() == 1


def test_rejecting_candidate_does_not_create_knowledge_entry(db_session):
    user = make_user(db_session, "maintenance-reject-user")
    service = MaintenanceCurationService(db_session)
    candidate = service.create_candidate(candidate_payload(), user)

    rejected = service.reject_candidate(candidate.id, user, "Insufficient evidence")

    assert rejected.status == MaintenanceExperienceCandidateStatus.rejected
    assert rejected.reviewed_by == user.id
    assert db_session.query(MaintenanceKnowledgeEntry).count() == 0
    assert db_session.query(AuditLog).filter_by(action="maintenance.experience_candidate.reject").count() == 1


def test_curation_does_not_modify_source_document_metadata_or_trigger_batch_reindex(db_session, tmp_path):
    user = make_user(db_session, "maintenance-safety-user")
    document = make_source_document(db_session, user, tmp_path)
    original_meta = dict(document.meta)
    service = MaintenanceCurationService(db_session)
    draft = service.create_record_draft(record_payload(), user)
    candidate = service.create_candidate(candidate_payload(draft.id), user)

    service.accept_candidate(candidate.id, user, "Approved")
    db_session.refresh(document)

    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert db_session.query(IndexJob).count() == 0
    assert db_session.query(MaintenanceExperienceCandidate).count() == 1
