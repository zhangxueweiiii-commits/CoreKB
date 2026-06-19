from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.documents import get_validation_report, list_document_validation_reports
from app.metadata import validate_metadata
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.services.validation_report_service import create_validation_report


def make_user(db_session, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db_session.add(user)
    db_session.flush()
    return user


def make_document(db_session, meta: dict | None = None) -> tuple[User, Document]:
    user = make_user(db_session, f"user-{uuid.uuid4().hex[:8]}")
    kb = KnowledgeBase(
        name=f"Validation API KB {uuid.uuid4().hex[:8]}",
        description="validation api",
        owner_id=user.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db_session.add(kb)
    db_session.flush()
    db_session.add(
        KBPermission(knowledge_base_id=kb.id, user_id=user.id, created_by=user.id, role=KBPermissionRole.owner)
    )
    document = Document(
        knowledge_base_id=kb.id,
        filename="manual.txt",
        file_path="/tmp/manual.txt",
        file_type="txt",
        file_size=12,
        status=DocumentStatus.indexed,
        chunk_count=0,
        meta=meta
        or {
            "title": "A200 Manual",
            "document_type": "manual",
            "department": "maintenance",
            "source": "internal",
        },
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(document)
    return user, document


def test_get_validation_report_by_id(db_session) -> None:
    user, document = make_document(db_session, meta={"title": "A200", "document_type": "spreadsheet"})
    report = create_validation_report(
        db_session,
        document_id=document.id,
        issues=validate_metadata(document.meta),
        summary="Invalid metadata",
    )

    response = get_validation_report(report.id, user, db_session)

    assert response["id"] == report.id
    assert response["document_id"] == document.id
    assert response["issue_count"] == report.issue_count
    assert response["severity"] == "error"
    assert response["status"] == "open"
    assert response["summary"] == "Invalid metadata"
    assert response["issues_json"][0]["code"] == "missing_required_field"


def test_get_missing_validation_report_returns_404(db_session) -> None:
    user, _document = make_document(db_session)

    with pytest.raises(HTTPException) as exc:
        get_validation_report(uuid.uuid4(), user, db_session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Validation report not found"


def test_list_reports_by_document_id(db_session) -> None:
    user, document = make_document(db_session, meta={"title": "A200", "document_type": "spreadsheet"})
    first = create_validation_report(db_session, document_id=document.id, issues=validate_metadata(document.meta))
    second = create_validation_report(db_session, document_id=document.id, issues=[])

    response = list_document_validation_reports(document.id, user, db_session)

    assert {item["id"] for item in response} == {first.id, second.id}
    assert all(item["document_id"] == document.id for item in response)


def test_list_reports_for_document_with_no_reports_returns_empty_list(db_session) -> None:
    user, document = make_document(db_session)

    response = list_document_validation_reports(document.id, user, db_session)

    assert response == []


def test_api_response_includes_report_fields(db_session) -> None:
    user, document = make_document(db_session, meta={"title": "", "document_type": "manual", "department": "m", "source": "internal"})
    report = create_validation_report(db_session, document_id=document.id, issues=validate_metadata(document.meta))

    response = get_validation_report(report.id, user, db_session)

    assert set(response) == {
        "id",
        "document_id",
        "report_type",
        "severity",
        "issue_count",
        "issues_json",
        "summary",
        "status",
        "created_at",
        "updated_at",
    }
    assert response["issue_count"] == 1
    assert response["severity"] == "error"
    assert response["status"] == "open"
    assert response["issues_json"][0]["code"] == "empty_value"


def test_validation_report_api_does_not_modify_document_metadata(db_session) -> None:
    user, document = make_document(db_session)
    before = dict(document.meta)
    report = create_validation_report(db_session, document_id=document.id, issues=[])

    get_validation_report(report.id, user, db_session)
    list_document_validation_reports(document.id, user, db_session)
    db_session.refresh(document)

    assert document.meta == before


def test_validation_report_api_does_not_create_suggestion_records(db_session) -> None:
    user, document = make_document(db_session)
    report = create_validation_report(db_session, document_id=document.id, issues=[])

    get_validation_report(report.id, user, db_session)
    list_document_validation_reports(document.id, user, db_session)

    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).count() == 0
