from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from app.models.alert_event import AlertEvent
from app.models.audit_log import AuditLog
from app.models.backup_job import BackupJob
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk
from app.models.evaluation_run import EvaluationRun
from app.models.index_job import IndexJob, IndexJobItem
from app.models.knowledge_base import KBPermission, KnowledgeBase
from app.models.retrieval_log import RetrievalLog
from app.models.user import User


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(*args, **kwargs) -> str:
    return "JSON"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    for table in [
        User.__table__,
        KnowledgeBase.__table__,
        KBPermission.__table__,
        Document.__table__,
        DocumentChunk.__table__,
        EvaluationRun.__table__,
        IndexJob.__table__,
        IndexJobItem.__table__,
        Conversation.__table__,
        Message.__table__,
        RetrievalLog.__table__,
        AuditLog.__table__,
        AlertEvent.__table__,
        BackupJob.__table__,
    ]:
        table.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        yield session
