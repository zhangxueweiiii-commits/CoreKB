from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.documents import accept_metadata_suggestion, generate_metadata_suggestions
from app.api.routes.metadata_dictionary import create_metadata_dictionary_entry
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.metadata_dictionary import MetadataDictionaryEntry
from app.models.user import User, UserRole
from app.schemas.document import DocumentMetadataSuggestionAcceptRequest
from app.schemas.metadata_dictionary import MetadataDictionaryEntryCreate
from app.services.metadata_dictionary_service import MetadataDictionaryService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name="Dictionary KB",
        description="dictionary",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def make_document(db, kb: KnowledgeBase, tmp_path: Path, filename: str) -> Document:
    path = tmp_path / filename
    path.write_text("A-200 ERR12 SOP001 MAT001", encoding="utf-8")
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta={},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def seed_dictionary(db, admin: User) -> None:
    service = MetadataDictionaryService(db)
    service.create_dictionary_entry("equipment_model", "A200", ["A-200", "EQ-A200"], admin)
    service.create_dictionary_entry("fault_code", "E12", ["E-12", "ERR12", "Error 12"], admin)
    service.create_dictionary_entry("sop_code", "SOP-001", ["SOP001", "SOP 001"], admin)
    service.create_dictionary_entry("material_code", "MAT-001", ["MAT001", "MAT 001"], admin)


def test_a_200_alias_normalizes_to_a200(db_session) -> None:
    admin = make_user(db_session, "dict-a200")
    seed_dictionary(db_session, admin)

    result = MetadataDictionaryService(db_session).normalize_with_dictionary("equipment_model", "A-200")

    assert result.normalized_value == "A200"
    assert result.matched_by == "alias"
    assert result.dictionary_entry_id is not None


def test_err12_alias_normalizes_to_e12(db_session) -> None:
    admin = make_user(db_session, "dict-e12")
    seed_dictionary(db_session, admin)

    result = MetadataDictionaryService(db_session).normalize_with_dictionary("fault_code", "ERR12")

    assert result.normalized_value == "E12"
    assert result.matched_by == "alias"


def test_sop001_alias_normalizes_to_sop_001(db_session) -> None:
    admin = make_user(db_session, "dict-sop")
    seed_dictionary(db_session, admin)

    result = MetadataDictionaryService(db_session).normalize_with_dictionary("sop_code", "SOP001")

    assert result.normalized_value == "SOP-001"
    assert result.matched_by == "alias"


def test_alias_conflict_is_rejected(db_session) -> None:
    admin = make_user(db_session, "dict-conflict")
    service = MetadataDictionaryService(db_session)
    service.create_dictionary_entry("equipment_model", "A200", ["A-200"], admin)

    with pytest.raises(ValueError):
        service.create_dictionary_entry("equipment_model", "B200", ["A-200"], admin)


def test_dictionary_miss_falls_back_to_rule_normalization(db_session) -> None:
    admin = make_user(db_session, "dict-rule")
    MetadataDictionaryService(db_session).create_dictionary_entry("equipment_model", "B300", ["B-300"], admin)

    result = MetadataDictionaryService(db_session).normalize_with_dictionary("equipment_model", "A-200")

    assert result.normalized_value == "A200"
    assert result.matched_by == "rule"
    assert result.dictionary_entry_id is None


def test_suggestion_saves_raw_and_normalized_values(db_session, tmp_path) -> None:
    admin = make_user(db_session, "dict-suggestion")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    document = make_document(db_session, kb, tmp_path, "A-200_ERR12.txt")

    generate_metadata_suggestions(document.id, admin, db_session)
    suggestion = db_session.query(DocumentMetadataSuggestion).filter_by(field="equipment_model").one()

    assert suggestion.raw_value == "A-200"
    assert suggestion.normalized_value == "A200"
    assert suggestion.suggested_value == "A200"
    assert suggestion.normalization_source == "alias"
    assert suggestion.dictionary_entry_id is not None


def test_accept_defaults_to_normalized_value(db_session, tmp_path, monkeypatch) -> None:
    from app.api.routes import documents as document_routes

    admin = make_user(db_session, "dict-accept")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    document = make_document(db_session, kb, tmp_path, "A-200.txt")
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)
    suggestion = generate_metadata_suggestions(document.id, admin, db_session)["items"][0]

    accept_metadata_suggestion(document.id, suggestion["id"], None, admin, db_session)
    db_session.refresh(document)

    assert document.meta["equipment_model"] == "A200"


def test_custom_value_does_not_create_dictionary_entry(db_session, tmp_path, monkeypatch) -> None:
    from app.api.routes import documents as document_routes

    admin = make_user(db_session, "dict-custom")
    kb = make_kb(db_session, admin)
    document = make_document(db_session, kb, tmp_path, "A-200.txt")
    monkeypatch.setattr(document_routes, "enqueue_reindex_job", lambda job_id: None)
    suggestion = generate_metadata_suggestions(document.id, admin, db_session)["items"][0]

    accept_metadata_suggestion(
        document.id,
        suggestion["id"],
        DocumentMetadataSuggestionAcceptRequest(value="Plant custom A-200", custom_value=True),
        admin,
        db_session,
    )
    db_session.refresh(document)

    assert document.meta["equipment_model"] == "Plant custom A-200"
    assert db_session.query(MetadataDictionaryEntry).count() == 0


def test_non_admin_cannot_manage_dictionary() -> None:
    viewer = User(username="viewer", password_hash="x", role=UserRole.viewer, is_active=True)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
