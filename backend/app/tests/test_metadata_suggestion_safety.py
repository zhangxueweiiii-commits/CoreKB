from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import documents as document_routes
from app.api.routes.documents import (
    accept_metadata_suggestion,
    generate_metadata_suggestions,
    reject_metadata_suggestion,
)
from app.core.request_context import RequestContext, set_request_context
from app.models.audit_log import AuditLog
from app.models.document import (
    Document,
    DocumentMetadataSuggestion,
    DocumentMetadataSuggestionConfidence,
    DocumentMetadataSuggestionSource,
    DocumentMetadataSuggestionStatus,
    DocumentStatus,
)
from app.models.index_job import IndexJob, IndexJobItem
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.schemas.document import DocumentMetadataSuggestionAcceptRequest


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=f"Metadata Safety KB {owner.username}",
        description="metadata safety",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def grant(db, kb: KnowledgeBase, user: User, role: KBPermissionRole) -> None:
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=user.id, created_by=kb.owner_id, role=role))
    db.commit()


def make_document(db, kb: KnowledgeBase, tmp_path: Path, meta=None, status: DocumentStatus = DocumentStatus.indexed) -> Document:
    filename = "A-200-maintenance-ERR12-V1.0.txt"
    path = tmp_path / filename
    path.write_text(
        "A-200 maintenance manual\nFault code Error 12 means temperature sensor abnormal.\nSOP001 Rev.A",
        encoding="utf-8",
    )
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=status,
        error_message="previous error" if status == DocumentStatus.failed else None,
        indexed_at=datetime.now(UTC) if status == DocumentStatus.indexed else None,
        chunk_count=1,
        meta=meta or {},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def first_suggestion_id(db, document: Document, field: str = "equipment_model"):
    suggestion = (
        db.query(DocumentMetadataSuggestion)
        .filter_by(document_id=document.id, field=field)
        .order_by(DocumentMetadataSuggestion.created_at.asc())
        .first()
    )
    assert suggestion is not None
    return suggestion.id


def test_generate_suggestions_does_not_modify_metadata_or_enqueue_reindex(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-generate-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"equipment_model": "MANUAL-A200", "owner_note": "keep me"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    calls: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: calls.append(str(job_id)))

    response = generate_metadata_suggestions(document.id, admin, db_session)
    db_session.refresh(document)

    assert response["total"] > 0
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert calls == []
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0
    assert db_session.query(IndexJobItem).count() == 0


def test_generate_suggestions_audit_log_excludes_source_content(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-safety-generate-audit-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)

    response = generate_metadata_suggestions(document.id, admin, db_session)

    audit = db_session.query(AuditLog).filter_by(action="document.metadata_suggestions.generate").one()
    assert audit.document_id == document.id
    assert audit.meta == {"suggestion_count": response["total"]}
    assert "content" not in audit.meta
    assert "file_content" not in audit.meta
    assert "evidence_excerpt" not in audit.meta


def test_reject_suggestion_does_not_modify_metadata_or_enqueue_reindex(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-reject-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"owner_note": "preserve"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    generate_metadata_suggestions(document.id, admin, db_session)
    suggestion_id = first_suggestion_id(db_session, document)
    calls: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: calls.append(str(job_id)))

    rejected = reject_metadata_suggestion(document.id, suggestion_id, admin, db_session)
    db_session.refresh(document)

    assert rejected["status"] == "rejected"
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert calls == []
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0
    audit = db_session.query(AuditLog).filter_by(action="document.metadata_suggestion.reject").one()
    assert audit.meta == {
        "field": "equipment_model",
        "suggestion_id": str(suggestion_id),
        "rejected_status": "rejected",
    }


def test_accept_suggestion_writes_only_target_field_and_enqueues_single_reindex(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-accept-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"owner_note": "preserve", "category": "maintenance"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    generate_metadata_suggestions(document.id, admin, db_session)
    suggestion_id = first_suggestion_id(db_session, document)
    enqueued_job_ids: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: enqueued_job_ids.append(str(job_id)))

    accepted = accept_metadata_suggestion(
        document.id,
        suggestion_id,
        DocumentMetadataSuggestionAcceptRequest(value="A-200"),
        admin,
        db_session,
    )
    db_session.refresh(document)

    assert accepted["status"] == "accepted"
    assert document.meta == {**original_meta, "equipment_model": "A200"}
    assert document.status == DocumentStatus.uploaded
    assert document.error_message is None
    assert document.indexed_at is None
    jobs = db_session.query(IndexJob).filter_by(document_id=document.id).all()
    assert len(jobs) == 1
    assert db_session.query(IndexJobItem).filter_by(job_id=jobs[0].id, document_id=document.id).count() == 1
    assert enqueued_job_ids == [str(jobs[0].id)]


def test_accept_suggestion_audit_log_is_traceable_without_full_source_content(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-accept-audit-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    generate_metadata_suggestions(document.id, admin, db_session)
    suggestion_id = first_suggestion_id(db_session, document)
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)

    accept_metadata_suggestion(
        document.id,
        suggestion_id,
        DocumentMetadataSuggestionAcceptRequest(value="A-200"),
        admin,
        db_session,
    )

    audit = db_session.query(AuditLog).filter_by(action="document.metadata_suggestion.accept").one()
    assert audit.document_id == document.id
    assert audit.meta["field"] == "equipment_model"
    assert audit.meta["value"] == "A200"
    assert audit.meta["suggestion_id"] == str(suggestion_id)
    assert audit.meta["index_job_id"]
    assert audit.meta["reindex_triggered"] is True
    assert audit.meta["custom_value"] is False
    assert "content" not in audit.meta
    assert "file_content" not in audit.meta
    assert "evidence_excerpt" not in audit.meta


def test_metadata_suggestion_audit_log_preserves_request_id_and_redaction_boundary(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-request-id-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)
    set_request_context(
        RequestContext(
            request_id="metadata-review-request-123",
            ip_address="10.0.0.8",
            user_agent="pytest-reviewer",
        )
    )

    try:
        generate_metadata_suggestions(document.id, admin, db_session)
        suggestion_id = first_suggestion_id(db_session, document)
        accept_metadata_suggestion(
            document.id,
            suggestion_id,
            DocumentMetadataSuggestionAcceptRequest(value="A-200"),
            admin,
            db_session,
        )
    finally:
        set_request_context(RequestContext())

    audits = db_session.query(AuditLog).order_by(AuditLog.created_at.asc()).all()
    assert [audit.action for audit in audits] == [
        "document.metadata_suggestions.generate",
        "document.metadata_suggestion.accept",
    ]
    for audit in audits:
        assert audit.request_id == "metadata-review-request-123"
        assert audit.ip_address == "10.0.0.8"
        assert audit.user_agent == "pytest-reviewer"
        assert "content" not in audit.meta
        assert "file_content" not in audit.meta
        assert "evidence_excerpt" not in audit.meta


def test_unsupported_suggestion_field_cannot_be_accepted_or_mutate_state(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-safety-unsupported-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"owner_note": "preserve"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    unsupported = DocumentMetadataSuggestion(
        document_id=document.id,
        field="unsupported_field",
        raw_value="value",
        normalized_value="value",
        normalization_source="fallback",
        suggested_value="value",
        confidence=DocumentMetadataSuggestionConfidence.high,
        source=DocumentMetadataSuggestionSource.filename,
        evidence_excerpt="unsupported value",
        rule_name="test_rule",
        status=DocumentMetadataSuggestionStatus.pending,
    )
    db_session.add(unsupported)
    db_session.commit()
    db_session.refresh(unsupported)
    calls: list[str] = []
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: calls.append(str(job_id)))

    with pytest.raises(HTTPException) as exc:
        accept_metadata_suggestion(document.id, unsupported.id, None, admin, db_session)
    db_session.refresh(document)
    db_session.refresh(unsupported)

    assert exc.value.status_code == 400
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert unsupported.status == DocumentMetadataSuggestionStatus.pending
    assert calls == []
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0
    assert db_session.query(AuditLog).filter_by(action="document.metadata_suggestion.accept").count() == 0


def test_viewer_cannot_generate_metadata_suggestions(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-safety-generate-permission-admin")
    viewer = make_user(db_session, "metadata-safety-viewer", UserRole.viewer)
    kb = make_kb(db_session, admin)
    grant(db_session, kb, viewer, KBPermissionRole.viewer)
    document = make_document(db_session, kb, tmp_path)

    with pytest.raises(HTTPException) as exc:
        generate_metadata_suggestions(document.id, viewer, db_session)

    assert exc.value.status_code == 403
    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).count() == 0
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0
    assert db_session.query(AuditLog).filter_by(action="document.metadata_suggestions.generate").count() == 0


def test_viewer_cannot_accept_metadata_suggestion_without_success_audit(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-safety-accept-permission-admin")
    viewer = make_user(db_session, "metadata-safety-accept-viewer", UserRole.viewer)
    kb = make_kb(db_session, admin)
    grant(db_session, kb, viewer, KBPermissionRole.viewer)
    document = make_document(db_session, kb, tmp_path)
    generate_metadata_suggestions(document.id, admin, db_session)
    suggestion_id = first_suggestion_id(db_session, document)

    with pytest.raises(HTTPException) as exc:
        accept_metadata_suggestion(document.id, suggestion_id, None, viewer, db_session)

    assert exc.value.status_code == 403
    assert db_session.query(AuditLog).filter_by(action="document.metadata_suggestion.accept").count() == 0

