import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from redis import Redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.document import Document
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.tasks.health_tasks import celery_health_check

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run real PostgreSQL/Qdrant/Redis integration tests.",
)


def integration_database_url() -> str:
    return os.getenv("INTEGRATION_DATABASE_URL") or get_settings().database_url


def run_migrations() -> None:
    settings = get_settings()
    settings.database_url = integration_database_url()
    config = Config("alembic.ini")
    command.upgrade(config, "head")


@pytest.fixture
def db_session():
    run_migrations()
    engine = create_engine(integration_database_url(), pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        yield session


def test_postgresql_schema_accepts_core_records(db_session) -> None:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"it_owner_{suffix}",
        email=f"it_owner_{suffix}@example.com",
        password_hash="x",
        role=UserRole.editor,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    kb = KnowledgeBase(name=f"it_kb_{suffix}", owner_id=user.id, visibility="private")
    db_session.add(kb)
    db_session.flush()
    permission = KBPermission(
        knowledge_base_id=kb.id,
        user_id=user.id,
        role=KBPermissionRole.owner,
        created_by=user.id,
    )
    db_session.add(permission)
    document = Document(
        knowledge_base_id=kb.id,
        filename="sample.txt",
        file_path="/tmp/sample.txt",
        file_type="txt",
        file_size=12,
    )
    db_session.add(document)
    db_session.commit()

    assert db_session.scalar(select(Document).where(Document.id == document.id)) is not None


def test_qdrant_upsert_search_and_delete_by_document_id() -> None:
    settings = get_settings()
    client = QdrantClient(url=os.getenv("QDRANT_URL") or settings.qdrant_url)
    collection = f"corekb_it_{uuid.uuid4().hex}"
    document_id = str(uuid.uuid4())
    point_id = str(uuid.uuid4())
    try:
      client.create_collection(
          collection_name=collection,
          vectors_config=qmodels.VectorParams(size=3, distance=qmodels.Distance.COSINE),
      )
      client.upsert(
          collection_name=collection,
          points=[
              qmodels.PointStruct(
                  id=point_id,
                  vector=[0.1, 0.2, 0.3],
                  payload={"document_id": document_id, "chunk_id": point_id},
              )
          ],
      )
      results = client.search(collection_name=collection, query_vector=[0.1, 0.2, 0.3], limit=1)
      assert results

      client.delete(
          collection_name=collection,
          points_selector=qmodels.FilterSelector(
              filter=qmodels.Filter(
                  must=[
                      qmodels.FieldCondition(
                          key="document_id", match=qmodels.MatchValue(value=document_id)
                      )
                  ]
              )
          ),
      )
      results_after_delete = client.search(
          collection_name=collection,
          query_vector=[0.1, 0.2, 0.3],
          limit=1,
      )
      assert results_after_delete == []
    finally:
      client.delete_collection(collection_name=collection)


def test_redis_and_celery_health_task() -> None:
    settings = get_settings()
    redis_url = os.getenv("REDIS_URL") or settings.redis_url
    redis_client = Redis.from_url(redis_url)
    assert redis_client.ping()

    result = celery_health_check.delay("integration-ok")
    assert result.get(timeout=15) == "integration-ok"
