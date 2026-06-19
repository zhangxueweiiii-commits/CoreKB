from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import documents as document_routes
from app.api.routes.documents import create_metadata_suggestions_from_validation_report
from app.models.audit_log import AuditLog
from app.models.document import Document, DocumentMetadataSuggestion, DocumentMetadataSuggestionStatus, DocumentStatus
from app.models.index_job import IndexJob, IndexJobItem
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.services.validation_report_service import create_validation_report


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=f"Validation Bridge KB {uuid.uuid4().hex[:8]}",
        description="validation bridge",
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


def make_document(db, kb: KnowledgeBase, tmp_path: Path, meta: dict | None = None) -> Document:
    path = tmp_path / "A-200-maintenance.txt"
    path.write_text("safe fixture content", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta=meta or {"owner_note": "preserve"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def metadata_issue(field: str, current_value: str | None, code: str = "invalid_enum") -> dict:
    return {
        "field": field,
        "code": code,
        "severity": "warning",
        "message": f"{field} should be normalized",
        "current_value": current_value,
        "expected": "canonical value",
    }


def test_bridge_creates_pending_suggestion_without_metadata_or_reindex(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "validation-bridge-admin")
    kb = make_kb(db_session, admin)
    original_meta = {"equipment_model": "A-200", "owner_note": "preserve"}
    document = make_document(db_session, kb, tmp_path, meta=original_meta)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("equipment_model", "A-200")],
        summary="Normalize equipment metadata",
    )
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: pytest.fail("must not enqueue reindex"))

    response = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)
    db_session.refresh(document)

    assert response["created_count"] == 1
    assert response["existing_count"] == 0
    assert response["skipped_count"] == 0
    assert response["items"][0]["field"] == "equipment_model"
    assert response["items"][0]["raw_value"] == "A-200"
    assert response["items"][0]["suggested_value"] == "A200"
    assert response["items"][0]["status"] == "pending"
    assert str(report.id) in response["items"][0]["evidence_excerpt"]
    assert document.meta == original_meta
    assert document.status == DocumentStatus.indexed
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 0
    assert db_session.query(IndexJobItem).count() == 0


def test_bridge_skips_unsupported_and_empty_issues(db_session, tmp_path) -> None:
    admin = make_user(db_session, "validation-bridge-skip-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[
            metadata_issue("title", "Pump Manual"),
            metadata_issue("equipment_model", None, "missing_required_field"),
        ],
    )

    response = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)

    assert response["created_count"] == 0
    assert response["skipped_count"] == 2
    assert {item["reason"] for item in response["skipped_issues"]} == {
        "unsupported_metadata_field",
        "missing_current_value",
    }
    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).count() == 0


def test_bridge_does_not_duplicate_existing_suggestion(db_session, tmp_path) -> None:
    admin = make_user(db_session, "validation-bridge-duplicate-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("fault_code", "ERR12")],
    )

    first = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)
    second = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)

    assert first["created_count"] == 1
    assert second["created_count"] == 0
    assert second["existing_count"] == 1
    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id, field="fault_code").count() == 1


def test_bridge_records_safe_audit_log(db_session, tmp_path) -> None:
    admin = make_user(db_session, "validation-bridge-audit-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("sop_code", "SOP001")],
    )

    create_metadata_suggestions_from_validation_report(report.id, admin, db_session)

    audit = db_session.query(AuditLog).filter_by(action="validation_report.metadata_suggestions.generate").one()
    assert audit.resource_id == str(report.id)
    assert audit.document_id == document.id
    assert audit.meta == {"created_count": 1, "existing_count": 0, "skipped_count": 0}
    assert "content" not in audit.meta
    assert "file_content" not in audit.meta
    assert "evidence_excerpt" not in audit.meta


def test_viewer_cannot_bridge_validation_report_to_suggestions(db_session, tmp_path) -> None:
    admin = make_user(db_session, "validation-bridge-permission-admin")
    viewer = make_user(db_session, "validation-bridge-viewer", UserRole.viewer)
    kb = make_kb(db_session, admin)
    grant(db_session, kb, viewer, KBPermissionRole.viewer)
    document = make_document(db_session, kb, tmp_path)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("equipment_model", "A-200")],
    )

    with pytest.raises(HTTPException) as exc:
        create_metadata_suggestions_from_validation_report(report.id, viewer, db_session)

    assert exc.value.status_code == 403
    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).count() == 0
    assert db_session.query(AuditLog).filter_by(action="validation_report.metadata_suggestions.generate").count() == 0


def test_document_type_issue_maps_to_doc_type_suggestion(db_session, tmp_path) -> None:
    admin = make_user(db_session, "validation-bridge-field-alias-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=[metadata_issue("document_type", "manual")],
    )

    response = create_metadata_suggestions_from_validation_report(report.id, admin, db_session)

    assert response["created_count"] == 1
    assert response["items"][0]["field"] == "doc_type"
    assert response["items"][0]["suggested_value"] == "manual"
    suggestion = db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).one()
    assert suggestion.status == DocumentMetadataSuggestionStatus.pending
