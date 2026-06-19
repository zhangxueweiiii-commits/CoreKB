import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import chat as chat_routes
from app.main import app
from app.models.conversation import Conversation
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.chat import ChatRequest
from app.services.chat_service import NO_EVIDENCE_ANSWER
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet


def make_user(db, username: str, role: UserRole = UserRole.viewer) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(name=f"kb-{uuid.uuid4().hex[:6]}", owner_id=owner.id, visibility="private")
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


async def read_stream(response) -> str:
    body = ""
    async for chunk in response.body_iterator:
        body += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
    return body


def test_chat_stream_requires_login() -> None:
    response = TestClient(app).post(
        "/api/chat/stream",
        json={"message": "hello", "knowledge_base_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_stream_rejects_unauthorized_kb(db_session) -> None:
    owner = make_user(db_session, "owner")
    outsider = make_user(db_session, "outsider")
    kb = make_kb(db_session, owner)

    with pytest.raises(HTTPException) as exc:
        await chat_routes.chat_stream(ChatRequest(message="hello", knowledge_base_ids=[kb.id]), outsider, db_session)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_chat_stream_no_evidence_returns_fixed_answer(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner")
    kb = make_kb(db_session, owner)

    class FakeRetrieval:
        async def search_with_options(self, **kwargs):
            return RetrievalResultSet(results=[])

    class FakeChatService:
        def __init__(self):
            self.retrieval_service = FakeRetrieval()

        def _get_or_create_conversation(self, db, user, message, knowledge_base_ids, conversation_id):
            conversation = Conversation(user_id=user.id, title=message, knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids])
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation

        def citations(self, results):
            return []

    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    response = await chat_routes.chat_stream(ChatRequest(message="missing", knowledge_base_ids=[kb.id]), owner, db_session)
    body = await read_stream(response)

    assert "event: retrieval_started" in body
    assert "event: retrieval_completed" in body
    assert f'"text": "{NO_EVIDENCE_ANSWER}"' in body
    assert "event: citations" in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_chat_stream_returns_token_and_citations_events(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner")
    kb = make_kb(db_session, owner)
    seen_kb_ids = []

    class FakeRetrieval:
        async def search_with_options(self, **kwargs):
            seen_kb_ids.extend(kwargs["knowledge_base_ids"])
            return RetrievalResultSet(
                results=[
                    RetrievedChunk(
                        chunk_text="CoreKB supports streaming answers.",
                        filename="guide.txt",
                        page_number=None,
                        score=0.91,
                        document_id=uuid.uuid4(),
                        chunk_id=uuid.uuid4(),
                        section_title="Chat",
                        metadata={},
                    )
                ]
            )

    class FakeLLM:
        async def stream_chat(self, messages):
            yield "CoreKB "
            yield "supports streaming."

    class FakeChatService:
        def __init__(self):
            self.retrieval_service = FakeRetrieval()
            self.llm_service = FakeLLM()

        def _get_or_create_conversation(self, db, user, message, knowledge_base_ids, conversation_id):
            conversation = Conversation(user_id=user.id, title=message, knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids])
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation

        def citations(self, results):
            return [{"filename": "guide.txt", "chunk_id": str(results[0].chunk_id), "quote": results[0].chunk_text}]

        def build_messages(self, message, results):
            return [{"role": "user", "content": message}]

    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    response = await chat_routes.chat_stream(ChatRequest(message="stream?", knowledge_base_ids=[kb.id]), owner, db_session)
    body = await read_stream(response)

    assert seen_kb_ids == [kb.id]
    assert 'event: token\ndata: {"text": "CoreKB "}' in body
    assert "event: citations" in body
    assert "guide.txt" in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_chat_stream_returns_error_event(db_session, monkeypatch) -> None:
    owner = make_user(db_session, "owner")
    kb = make_kb(db_session, owner)

    class BrokenRetrieval:
        async def search_with_options(self, **kwargs):
            raise RuntimeError("vector store unavailable")

    class FakeChatService:
        def __init__(self):
            self.retrieval_service = BrokenRetrieval()

        def _get_or_create_conversation(self, db, user, message, knowledge_base_ids, conversation_id):
            conversation = Conversation(user_id=user.id, title=message, knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids])
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation

    monkeypatch.setattr(chat_routes, "ChatService", FakeChatService)

    response = await chat_routes.chat_stream(ChatRequest(message="boom", knowledge_base_ids=[kb.id]), owner, db_session)
    body = await read_stream(response)

    assert "event: error" in body
    assert "vector store unavailable" in body
