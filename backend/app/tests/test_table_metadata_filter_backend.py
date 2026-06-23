import uuid

import pytest

from app.api.routes import search as search_routes
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.search import SearchRequest
from app.services.query_metadata_extractor import sanitize_metadata_filter
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet
from app.services.vector_store import build_qdrant_metadata_filter


def make_user(db, username: str, role: UserRole = UserRole.editor) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User, name: str = "table-filter-kb") -> KnowledgeBase:
    kb = KnowledgeBase(name=name, owner_id=owner.id, visibility="private")
    db.add(kb)
    db.flush()
    db.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=owner.id,
            role=KBPermissionRole.owner,
            created_by=owner.id,
        )
    )
    db.commit()
    db.refresh(kb)
    return kb


def condition_values(conditions):
    return {condition.key: condition.match.value for condition in conditions}


def test_sanitize_metadata_filter_allows_table_fields() -> None:
    sanitized = sanitize_metadata_filter(
        {
            "source_type": "table",
            "sheet_name": "Products",
            "table_index": "0",
            "row_start": "4",
            "row_end": 6,
            "column_names": "material_code",
        }
    )

    assert sanitized == {
        "source_type": "table",
        "sheet_name": "Products",
        "table_index": 0,
        "row_start": 4,
        "row_end": 6,
    }


def test_sanitize_metadata_filter_ignores_invalid_numeric_table_fields() -> None:
    sanitized = sanitize_metadata_filter(
        {
            "source_type": "table",
            "row_start": "first",
            "row_end": "",
            "table_index": None,
        }
    )

    assert sanitized == {"source_type": "table"}


def test_build_qdrant_metadata_filter_uses_typed_table_values() -> None:
    conditions = build_qdrant_metadata_filter(
        {
            "source_type": "table",
            "sheet_name": "Products",
            "row_start": "4",
            "row_end": 6,
        }
    )

    assert condition_values(conditions) == {
        "source_type": "table",
        "sheet_name": "Products",
        "row_start": 4,
        "row_end": 6,
    }


@pytest.mark.asyncio
async def test_search_api_passes_table_metadata_filter(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "table-filter-owner")
    kb = make_kb(db_session, owner)
    seen_filter = {}

    class FakeRetrievalService:
        async def search_with_options(self, **kwargs):
            seen_filter.update(kwargs["metadata_filter"])
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="Sheet: Products\nRows: 4-6\nmaterial_code: P-A200-H",
                        filename="material_parameters.xlsx",
                        page_number=None,
                        score=0.9,
                        document_id=uuid.uuid4(),
                        chunk_id=uuid.uuid4(),
                        section_title="Products",
                        metadata={
                            "source_type": "table",
                            "sheet_name": "Products",
                            "row_start": 4,
                            "row_end": 6,
                        },
                        vector_score=0.9,
                        final_score=0.9,
                    )
                ]
            )

    monkeypatch.setattr(search_routes, "RetrievalService", FakeRetrievalService)

    response = await search_routes.search(
        SearchRequest(
            query="P-A200-H protocol",
            knowledge_base_ids=[kb.id],
            metadata_filter={
                "source_type": "table",
                "sheet_name": "Products",
                "row_start": "4",
                "row_end": "6",
                "unsupported": "ignored",
            },
        ),
        owner,
        db_session,
    )

    assert seen_filter == {
        "source_type": "table",
        "sheet_name": "Products",
        "row_start": 4,
        "row_end": 6,
    }
    assert response.results[0].sheet_name == "Products"
    assert response.results[0].row_start == 4
    assert response.results[0].row_end == 6
