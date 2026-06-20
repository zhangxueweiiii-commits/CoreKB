from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes.documents import get_document_table_preview
from app.models.document import Document, DocumentMetadataSuggestion, DocumentStatus
from app.models.index_job import IndexJob
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase, KnowledgeBaseVisibility
from app.models.user import User, UserRole


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(
        name="Table Preview KB",
        description="table preview",
        owner_id=owner.id,
        visibility=KnowledgeBaseVisibility.private,
    )
    db.add(kb)
    db.flush()
    db.add(KBPermission(knowledge_base_id=kb.id, user_id=owner.id, created_by=owner.id, role=KBPermissionRole.owner))
    db.commit()
    db.refresh(kb)
    return kb


def make_document(db, kb: KnowledgeBase, path: Path, file_type: str, meta=None) -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type=file_type,
        file_size=path.stat().st_size,
        status=DocumentStatus.indexed,
        chunk_count=0,
        meta=meta or {},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_table_preview_returns_csv_rows(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-preview-admin")
    kb = make_kb(db_session, admin)
    path = tmp_path / "products.csv"
    path.write_text("model,voltage,power\nA100,220V,500W\nA200,380V,1200W\n", encoding="utf-8")
    document = make_document(db_session, kb, path, "csv", meta={"category": "material"})

    response = get_document_table_preview(document.id, 50, admin, db_session)

    assert response["document_id"] == document.id
    assert response["filename"] == "products.csv"
    assert response["tables"][0]["sheet_name"] == "CSV"
    assert response["tables"][0]["headers"] == ["model", "voltage", "power"]
    assert response["tables"][0]["source_range"] == "2-3"
    assert response["tables"][0]["rows"][0] == {
        "row_number": 2,
        "values": {"model": "A100", "voltage": "220V", "power": "500W"},
        "raw_text": "model: A100; voltage: 220V; power: 500W",
    }


def test_table_preview_truncates_rows(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-preview-truncate-admin")
    kb = make_kb(db_session, admin)
    path = tmp_path / "long.csv"
    path.write_text("model\nA100\nA200\nA300\n", encoding="utf-8")
    document = make_document(db_session, kb, path, "csv")

    response = get_document_table_preview(document.id, 2, admin, db_session)

    table = response["tables"][0]
    assert table["row_count"] == 3
    assert [row["row_number"] for row in table["rows"]] == [2, 3]
    assert table["truncated"] is True


def test_table_preview_rejects_non_table_documents(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-preview-non-table-admin")
    kb = make_kb(db_session, admin)
    path = tmp_path / "manual.txt"
    path.write_text("plain text", encoding="utf-8")
    document = make_document(db_session, kb, path, "txt")

    with pytest.raises(HTTPException) as exc:
        get_document_table_preview(document.id, 50, admin, db_session)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Document is not a table file"


def test_table_preview_is_read_only(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "table-preview-readonly-admin")
    kb = make_kb(db_session, admin)
    path = tmp_path / "products.csv"
    path.write_text("model\nA100\n", encoding="utf-8")
    document = make_document(db_session, kb, path, "csv", meta={"product_model": "A100"})

    response = get_document_table_preview(document.id, 50, admin, db_session)
    db_session.refresh(document)

    assert response["tables"][0]["rows"][0]["values"]["model"] == "A100"
    assert document.meta == {"product_model": "A100"}
    assert db_session.query(DocumentMetadataSuggestion).count() == 0
    assert db_session.query(IndexJob).count() == 0