from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

from app.api.routes import documents as document_routes
from app.api.routes.documents import (
    accept_metadata_suggestion,
    create_metadata_suggestions_from_validation_report,
    get_validation_report,
    list_document_validation_reports,
    reject_metadata_suggestion,
)
from app.models.audit_log import AuditLog
from app.models.document import Document, DocumentMetadataSuggestion, DocumentMetadataSuggestionStatus, DocumentStatus
from app.models.index_job import IndexJob, IndexJobItem
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.schemas.document import DocumentMetadataSuggestionAcceptRequest
from app.services.validation_report_service import create_validation_report


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=f"Closed Loop KB {uuid.uuid4().hex[:8]}",
        description="closed loop verification",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def make_document(db, kb: KnowledgeBase, tmp_path: Path, meta: dict | None = None) -> Document:
    path = tmp_path / "A-200-maintenance-ERR12.txt"
    path.write_text("A-200 maintenance manual with ERR12 fault code", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        indexed_at=datetime.now(UTC),
        chunk_count=1,
        meta=meta or {"owner_note": "preserve"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def metadata_issue(field: str, current_value: str, expected: str) -> dict:
    return {
        "field": field,
        "code": "invalid_enum",
        "severity": "warning",
        "message": f"{field} should be normalized before metadata filtering",
        "current_value": current_value,
        "expected": expected,
    }


def test_closed_loop_report_to_pending_suggestion_to_explicit_accept(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "closed-loop-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"owner_note": "preserve"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("equipment_model", "A-200", "A200")],
        summary="Equipment model should be canonicalized.",
    )
    enqueued_job_ids: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: enqueued_job_ids.append(str(job_id)))

    listed_reports = list_document_validation_reports(document.id, admin, db_session)
    fetched_report = get_validation_report(report.id, admin, db_session)
    bridge_response = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)
    db_session.refresh(document)

    assert [item["id"] for item in listed_reports] == [report.id]
    assert fetched_report["issue_count"] == 1
    assert bridge_response["created_count"] == 1
    assert bridge_response["items"][0]["field"] == "equipment_model"
    assert bridge_response["items"][0]["suggested_value"] == "A200"
    assert bridge_response["items"][0]["status"] == "pending"
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert enqueued_job_ids == []
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0

    suggestion = db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).one()
    accepted = accept_metadata_suggestion(
        document.id,
        suggestion.id,
        DocumentMetadataSuggestionAcceptRequest(value="A-200"),
        admin,
        db_session,
    )
    db_session.refresh(document)

    assert accepted["status"] == "accepted"
    assert document.meta == {"owner_note": "preserve", "equipment_model": "A200"}
    assert document.status == DocumentStatus.uploaded
    jobs = db_session.query(IndexJob).filter_by(document_id=document.id).all()
    assert len(jobs) == 1
    assert db_session.query(IndexJobItem).filter_by(job_id=jobs[0].id, document_id=document.id).count() == 1
    assert enqueued_job_ids == [str(jobs[0].id)]

    actions = [audit.action for audit in db_session.query(AuditLog).order_by(AuditLog.created_at.asc()).all()]
    assert actions == [
        "validation_report.metadata_suggestions.generate",
        "document.metadata_suggestion.accept",
    ]


def test_closed_loop_reject_keeps_metadata_and_index_state_unchanged(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "closed-loop-reject-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"owner_note": "preserve"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("fault_code", "ERR12", "E12")],
        summary="Fault code should be canonicalized.",
    )
    enqueued_job_ids: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: enqueued_job_ids.append(str(job_id)))

    create_metadata_suggestions_from_validation_report(report.id, admin, db_session)
    suggestion = db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).one()
    rejected = reject_metadata_suggestion(document.id, suggestion.id, admin, db_session)
    db_session.refresh(document)
    db_session.refresh(suggestion)

    assert rejected["status"] == "rejected"
    assert suggestion.status == DocumentMetadataSuggestionStatus.rejected
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert enqueued_job_ids == []
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0

    audits = db_session.query(AuditLog).order_by(AuditLog.created_at.asc()).all()
    assert [audit.action for audit in audits] == [
        "validation_report.metadata_suggestions.generate",
        "document.metadata_suggestion.reject",
    ]
