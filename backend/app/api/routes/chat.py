import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.metrics import CHAT_REQUESTS_TOTAL
from app.core.tracing import start_span
from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationRead
from app.services.audit_service import AuditService
from app.services.chat_service import ChatService, NO_EVIDENCE_ANSWER, resolve_chat_metadata_filter
from app.services.permission_service import PermissionService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    accessible_kb_ids = PermissionService(db).filter_accessible_kb_ids(
        current_user, payload.knowledge_base_ids
    )
    if not accessible_kb_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No accessible knowledge bases")
    try:
        with start_span("chat.ask", kb_count=len(accessible_kb_ids), stream=False):
            answer_result = await ChatService().answer(
                db=db,
                user=current_user,
                message=payload.message,
                knowledge_base_ids=accessible_kb_ids,
                conversation_id=payload.conversation_id,
                metadata_filter=payload.metadata_filter,
                auto_metadata_filter=payload.auto_metadata_filter,
                use_rerank=payload.use_rerank,
                rerank_top_n=payload.rerank_top_n,
            )
            (
                answer,
                citations,
                conversation,
                used_metadata_filter,
                rerank_applied,
                rerank_error,
                *_optional_trace,
            ) = answer_result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    CHAT_REQUESTS_TOTAL.labels("regular").inc()
    AuditService(db).record(
        actor=current_user,
        action="chat.ask",
        resource_type="chat",
        resource_id=conversation.id,
        status="success",
        metadata={
            "message_preview": payload.message[:200],
            "knowledge_base_ids": [str(kb_id) for kb_id in accessible_kb_ids],
            "metadata_filter": used_metadata_filter,
            "use_rerank": payload.use_rerank,
            "rerank_applied": rerank_applied,
            "rerank_error": rerank_error,
        },
    )
    return ChatResponse(
        answer=answer,
        citations=citations,
        conversation_id=conversation.id,
        used_metadata_filter=used_metadata_filter,
        use_rerank=payload.use_rerank,
        rerank_applied=rerank_applied,
        rerank_error=rerank_error,
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    accessible_kb_ids = PermissionService(db).filter_accessible_kb_ids(
        current_user, payload.knowledge_base_ids
    )
    if not accessible_kb_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No accessible knowledge bases")

    async def events():
        service = ChatService()
        answer_parts: list[str] = []
        citations: list[dict] = []
        conversation: Conversation | None = None
        used_metadata_filter: dict = {}
        rerank_applied = False
        rerank_error: str | None = None
        try:
            with start_span("chat.stream", kb_count=len(accessible_kb_ids), stream=True):
                yield _sse("retrieval_started", {"message": "开始检索知识库"})
                conversation = service._get_or_create_conversation(
                    db,
                    current_user,
                    payload.message,
                    accessible_kb_ids,
                    payload.conversation_id,
                )
                used_metadata_filter = resolve_chat_metadata_filter(
                    payload.message,
                    payload.metadata_filter,
                    payload.auto_metadata_filter,
                )
                result_set = await service.retrieval_service.search_with_options(
                    db=db,
                    user=current_user,
                    query=payload.message,
                    knowledge_base_ids=accessible_kb_ids,
                    top_k=5,
                    score_threshold=None,
                    metadata_filter=used_metadata_filter,
                    use_rerank=payload.use_rerank,
                    rerank_top_n=payload.rerank_top_n,
                )
                results = result_set.results
                rerank_applied = result_set.rerank_applied
                rerank_error = result_set.rerank_error
                citations = service.citations(results)
                yield _sse(
                    "retrieval_completed",
                    {
                        "chunk_count": len(results),
                        "used_metadata_filter": used_metadata_filter,
                        "use_rerank": payload.use_rerank,
                        "rerank_applied": rerank_applied,
                        "rerank_error": rerank_error,
                    },
                )
                if not results:
                    answer_parts.append(NO_EVIDENCE_ANSWER)
                    yield _sse("token", {"text": NO_EVIDENCE_ANSWER})
                else:
                    async for token in service.llm_service.stream_chat(service.build_messages(payload.message, results)):
                        answer_parts.append(token)
                        yield _sse("token", {"text": token})
            answer = "".join(answer_parts).strip() or NO_EVIDENCE_ANSWER
            persisted_citations = citations if answer != NO_EVIDENCE_ANSWER else []
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=payload.message,
                    citations=[],
                    knowledge_base_ids=[str(kb_id) for kb_id in accessible_kb_ids],
                )
            )
            db.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=answer,
                    citations=persisted_citations,
                    knowledge_base_ids=[str(kb_id) for kb_id in accessible_kb_ids],
                )
            )
            db.commit()
            CHAT_REQUESTS_TOTAL.labels("stream").inc()
            AuditService(db).record(
                actor=current_user,
                action="chat.ask",
                resource_type="chat",
                resource_id=conversation.id,
                status="success",
                metadata={
                    "stream": True,
                    "message_preview": payload.message[:200],
                    "knowledge_base_ids": [str(kb_id) for kb_id in accessible_kb_ids],
                    "metadata_filter": used_metadata_filter,
                    "use_rerank": payload.use_rerank,
                    "rerank_applied": rerank_applied,
                    "rerank_error": rerank_error,
                },
            )
            yield _sse("citations", persisted_citations)
            yield _sse(
                "done",
                {
                    "conversation_id": str(conversation.id),
                    "used_metadata_filter": used_metadata_filter,
                    "use_rerank": payload.use_rerank,
                    "rerank_applied": rerank_applied,
                    "rerank_error": rerank_error,
                },
            )
        except ValueError as exc:
            yield _sse("error", {"message": str(exc)})
        except Exception as exc:
            db.rollback()
            if conversation:
                AuditService(db).record(
                    actor=current_user,
                    action="chat.ask",
                    resource_type="chat",
                    resource_id=conversation.id,
                    status="failed",
                    error_message=str(exc),
                    metadata={"stream": True, "message_preview": payload.message[:200]},
                )
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.updated_at.desc())
        ).all()
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .options(selectinload(Conversation.messages))
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation
