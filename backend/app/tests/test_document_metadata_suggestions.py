from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import documents as document_routes
from app.api.routes.documents import (
    accept_metadata_suggestion,
    generate_metadata_suggestions,
    reject_metadata_suggestion,
)
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.index_job import IndexJob
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.schemas.document import DocumentMetadataSuggestionAcceptRequest
from app.services.document_metadata_completeness_service import DocumentMetadataCompletenessService
from app.services.document_metadata_suggester import DocumentMetadataSuggester


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name="Metadata KB",
        description="metadata",
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


def make_document(db, kb: KnowledgeBase, tmp_path: Path, filename: str = "A-200维修手册_ERR12_V1.0.txt", meta=None) -> Document:
    path = tmp_path / filename
    path.write_text(
        "A-200 设备维修手册\n故障码 Error 12 表示温度传感器异常。\n作业指导书 SOP001 Rev.A",
        encoding="utf-8",
    )
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta=meta or {},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_filename_a_200_normalizes_to_a200() -> None:
    candidates = DocumentMetadataSuggester().extract_metadata_from_filename("A-200维修手册.txt")
    values = {(item.field, item.suggested_value) for item in candidates}

    assert ("equipment_model", "A200") in values


def test_fault_code_variants_normalize_to_e12() -> None:
    suggester = DocumentMetadataSuggester()

    assert suggester.normalize_metadata_value("fault_code", "ERR12") == "E12"
    assert suggester.normalize_metadata_value("fault_code", "Error 12") == "E12"
    assert suggester.normalize_metadata_value("fault_code", "E-12") == "E12"


def test_sop001_normalizes_to_sop_001() -> None:
    assert DocumentMetadataSuggester().normalize_metadata_value("sop_code", "SOP001") == "SOP-001"


def test_existing_metadata_is_not_overwritten_by_generate(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-generate-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path, meta={"equipment_model": "MANUAL-A200"})

    generate_metadata_suggestions(document.id, admin, db_session)
    db_session.refresh(document)

    assert document.meta["equipment_model"] == "MANUAL-A200"


def test_duplicate_generate_does_not_duplicate_suggestion(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-duplicate-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)

    generate_metadata_suggestions(document.id, admin, db_session)
    generate_metadata_suggestions(document.id, admin, db_session)

    rows = db_session.query(DocumentMetadataSuggestion).filter_by(
        document_id=document.id,
        field="equipment_model",
        suggested_value="A200",
    ).all()
    assert len(rows) == 1


def test_accept_updates_document_metadata_and_creates_index_job(db_session, tmp_path, monkeypatch) -> None:
    admin = make_user(db_session, "metadata-accept-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)
    suggestions = generate_metadata_suggestions(document.id, admin, db_session)["items"]
    suggestion_id = next(item["id"] for item in suggestions if item["field"] == "equipment_model")

    accepted = accept_metadata_suggestion(
        document.id,
        suggestion_id,
        DocumentMetadataSuggestionAcceptRequest(value="A-200"),
        admin,
        db_session,
    )
    db_session.refresh(document)

    assert accepted["status"] == "accepted"
    assert document.meta["equipment_model"] == "A200"
    assert db_session.query(IndexJob).filter_by(document_id=document.id).count() == 1


def test_reject_does_not_update_document_metadata(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-reject-admin")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path)
    suggestions = generate_metadata_suggestions(document.id, admin, db_session)["items"]
    suggestion_id = next(item["id"] for item in suggestions if item["field"] == "equipment_model")

    rejected = reject_metadata_suggestion(document.id, suggestion_id, admin, db_session)
    db_session.refresh(document)

    assert rejected["status"] == "rejected"
    assert "equipment_model" not in document.meta


def test_metadata_completeness_for_categories(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-completeness-admin")
    kb = make_kb(db_session, admin)
    service = DocumentMetadataCompletenessService()

    maintenance = make_document(db_session, kb, tmp_path, filename="m.txt", meta={"category": "maintenance", "equipment_model": "A200"})
    quality = make_document(db_session, kb, tmp_path, filename="q.txt", meta={"category": "quality", "doc_type": "检验规范", "version": "V1.0", "effective_date": "2026-01-01"})
    sop = make_document(db_session, kb, tmp_path, filename="s.txt", meta={"category": "sop", "sop_code": "SOP-001", "process_name": "点检", "version": "V1.0"})
    material = make_document(db_session, kb, tmp_path, filename="p.txt", meta={"category": "material", "material_code": "MAT-001", "version": "V1.0"})

    assert service.evaluate(maintenance)["completeness_status"] == "partial"
    assert service.evaluate(quality)["completeness_status"] == "complete"
    assert service.evaluate(sop)["completeness_status"] == "complete"
    assert service.evaluate(material)["completeness_status"] == "complete"


def test_viewer_cannot_accept_metadata_suggestion(db_session, tmp_path) -> None:
    admin = make_user(db_session, "metadata-permission-admin")
    viewer = make_user(db_session, "metadata-viewer", UserRole.viewer)
    kb = make_kb(db_session, admin)
    grant(db_session, kb, viewer, KBPermissionRole.viewer)
    document = make_document(db_session, kb, tmp_path)
    suggestion = generate_metadata_suggestions(document.id, admin, db_session)["items"][0]

    with pytest.raises(HTTPException) as exc:
        accept_metadata_suggestion(document.id, suggestion["id"], None, viewer, db_session)

    assert exc.value.status_code == 403
