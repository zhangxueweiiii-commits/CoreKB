import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.metadata import metadata_precheck
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.index_job import IndexJob
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole
from app.services.metadata_dictionary_service import MetadataDictionaryService
from app.services.metadata_normalization_precheck_service import MetadataNormalizationPrecheckService


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User, name: str = "Precheck KB") -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description="precheck",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def make_document(db, kb: KnowledgeBase, filename: str, meta: dict) -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=f"/tmp/{filename}",
        file_type="txt",
        file_size=10,
        status=DocumentStatus.indexed,
        chunk_count=1,
        meta=meta,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def seed_dictionary(db, admin: User) -> None:
    service = MetadataDictionaryService(db)
    service.create_dictionary_entry("equipment_model", "A200", ["A-200"], admin)
    service.create_dictionary_entry("fault_code", "E12", ["ERR12"], admin)


def item_for(result: dict, field_name: str):
    return next(item for item in result["items"] if item["field_name"] == field_name)


def test_canonical_value_is_detected(db_session) -> None:
    admin = make_user(db_session, "precheck-canonical")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    make_document(db_session, kb, "a200.txt", {"equipment_model": "A200"})

    result = MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    item = item_for(result, "equipment_model")

    assert item["status"] == "canonical"
    assert item["recommended_action"] == "no_action"


def test_alias_match_suggests_canonical(db_session) -> None:
    admin = make_user(db_session, "precheck-alias")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    make_document(db_session, kb, "a-200.txt", {"equipment_model": "A-200"})

    result = MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    item = item_for(result, "equipment_model")

    assert item["status"] == "alias_match"
    assert item["suggested_value"] == "A200"
    assert item["matched_by"] == "dictionary_alias"


def test_sop001_without_dictionary_alias_is_rule_normalizable(db_session) -> None:
    admin = make_user(db_session, "precheck-sop")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    make_document(db_session, kb, "sop.txt", {"sop_code": "SOP001"})

    result = MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    item = item_for(result, "sop_code")

    assert item["status"] == "rule_normalizable"
    assert item["suggested_value"] == "SOP-001"


def test_unregistered_model_is_dictionary_missing(db_session) -> None:
    admin = make_user(db_session, "precheck-missing")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    make_document(db_session, kb, "x900.txt", {"equipment_model": "X900"})

    result = MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    item = item_for(result, "equipment_model")

    assert item["status"] == "dictionary_missing"
    assert item["recommended_action"] == "add_dictionary_entry"


@pytest.mark.parametrize("value", ["N/A", "未知", "-"])
def test_invalid_or_empty_values_are_detected(db_session, value) -> None:
    admin = make_user(db_session, f"precheck-invalid-{value}")
    kb = make_kb(db_session, admin)
    make_document(db_session, kb, "invalid.txt", {"fault_code": value})

    result = MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    item = item_for(result, "fault_code")

    assert item["status"] == "invalid_or_empty"
    assert item["recommended_action"] == "review_invalid_value"


def test_precheck_is_read_only(db_session) -> None:
    admin = make_user(db_session, "precheck-readonly")
    kb = make_kb(db_session, admin)
    seed_dictionary(db_session, admin)
    document = make_document(db_session, kb, "readonly.txt", {"equipment_model": "A-200"})
    before_meta = dict(document.meta)

    MetadataNormalizationPrecheckService(db_session).run_metadata_normalization_precheck()
    db_session.refresh(document)

    assert document.meta == before_meta
    assert db_session.query(DocumentMetadataSuggestion).count() == 0
    assert db_session.query(IndexJob).count() == 0


def test_precheck_filters_by_kb_field_and_status(db_session) -> None:
    admin = make_user(db_session, "precheck-filter")
    kb_1 = make_kb(db_session, admin, "KB1")
    kb_2 = make_kb(db_session, admin, "KB2")
    seed_dictionary(db_session, admin)
    make_document(db_session, kb_1, "alias.txt", {"equipment_model": "A-200"})
    make_document(db_session, kb_2, "canonical.txt", {"equipment_model": "A200"})

    result = metadata_precheck(
        knowledge_base_id=kb_1.id,
        field_name="equipment_model",
        status_filter="alias_match",
        _=admin,
        db=db_session,
    )

    assert result["total"] == 1
    assert result["items"][0]["knowledge_base_id"] == kb_1.id
    assert result["items"][0]["status"] == "alias_match"


def test_non_admin_cannot_access_precheck_api() -> None:
    viewer = User(username="viewer", password_hash="x", role=UserRole.viewer, is_active=True)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403
