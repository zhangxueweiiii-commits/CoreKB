from __future__ import annotations

from app.metadata import validate_metadata
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.services.validation_report_service import (
    create_validation_report,
    get_validation_report,
    list_validation_reports_by_document,
)


def make_document(db_session, meta: dict | None = None) -> Document:
    user = User(username="validation-report-admin", password_hash="x", role=UserRole.admin, is_active=True)
    db_session.add(user)
    db_session.flush()
    kb = KnowledgeBase(
        name="Validation Report KB",
        description="validation",
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
        meta=meta or {
            "title": "A200 Manual",
            "document_type": "manual",
            "department": "maintenance",
            "source": "internal",
        },
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_create_validation_report_from_zero_issues(db_session) -> None:
    document = make_document(db_session)

    report = create_validation_report(db_session, document_id=document.id, issues=[], summary="No issues")

    assert report.issue_count == 0
    assert report.severity.value == "info"
    assert report.issues_json == []
    assert report.summary == "No issues"
    assert report.status.value == "open"


def test_create_validation_report_from_one_issue(db_session) -> None:
    document = make_document(db_session, meta={"document_type": "manual"})
    issues = validate_metadata(document.meta)

    report = create_validation_report(db_session, document_id=document.id, issues=issues)

    assert report.issue_count == 3
    assert report.severity.value == "error"
    assert report.issues_json[0]["code"] == "missing_required_field"


def test_create_validation_report_from_multiple_issues(db_session) -> None:
    document = make_document(
        db_session,
        meta={
            "title": "",
            "document_type": "spreadsheet",
            "department": "maintenance",
            "source": "internal",
            "tags": "A200",
            "legacy_field": "legacy",
        },
    )
    issues = validate_metadata(document.meta)

    report = create_validation_report(db_session, document_id=document.id, issues=issues)

    assert report.issue_count == 4
    assert report.severity.value == "error"
    assert {issue["code"] for issue in report.issues_json} == {
        "empty_value",
        "invalid_enum",
        "invalid_type",
        "unknown_field",
    }


def test_highest_severity_is_computed_correctly(db_session) -> None:
    document = make_document(db_session, meta={"title": "A200", "document_type": "manual", "department": "m", "source": "internal", "extra": "x"})
    issues = validate_metadata(document.meta)

    report = create_validation_report(db_session, document_id=document.id, issues=issues)

    assert report.issue_count == 1
    assert report.severity.value == "warning"


def test_issues_json_preserves_structured_issue_content(db_session) -> None:
    document = make_document(db_session, meta={"title": "A200", "document_type": "spreadsheet", "department": "m", "source": "internal"})
    issues = validate_metadata(document.meta)

    report = create_validation_report(db_session, document_id=document.id, issues=issues)

    assert report.issues_json == [
        {
            "field": "document_type",
            "code": "invalid_enum",
            "severity": "error",
            "message": "Metadata field 'document_type' is not an allowed value.",
            "current_value": "spreadsheet",
            "expected": ["manual", "policy", "report", "work_order", "invoice", "bom", "unknown"],
        }
    ]


def test_get_report_by_id_and_list_reports_by_document(db_session) -> None:
    document = make_document(db_session)
    first = create_validation_report(db_session, document_id=document.id, issues=[], summary="first")
    second = create_validation_report(db_session, document_id=document.id, issues=[], summary="second")

    loaded = get_validation_report(db_session, first.id)
    reports = list_validation_reports_by_document(db_session, document.id)

    assert loaded is not None
    assert loaded.id == first.id
    assert {report.id for report in reports} == {first.id, second.id}


def test_create_report_does_not_modify_document_metadata(db_session) -> None:
    document = make_document(db_session)
    before = dict(document.meta)

    create_validation_report(db_session, document_id=document.id, issues=validate_metadata(document.meta))
    db_session.refresh(document)

    assert document.meta == before


def test_create_report_does_not_create_metadata_suggestions(db_session) -> None:
    document = make_document(db_session)

    create_validation_report(db_session, document_id=document.id, issues=validate_metadata(document.meta))

    assert db_session.query(DocumentMetadataSuggestion).filter_by(document_id=document.id).count() == 0
