from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KBPermission, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_preset_service import AssistantPreset, get_assistant_preset
from app.services.chat_service import ChatService, NO_EVIDENCE_ANSWER


class AssistantService:
    def __init__(self, chat_service: ChatService | None = None) -> None:
        self.chat_service = chat_service or ChatService()

    def accessible_kb_ids(self, db: Session, user: User) -> list[UUID]:
        if user.role == UserRole.admin:
            return list(db.scalars(select(KnowledgeBase.id)).all())
        rows = db.scalars(
            select(KnowledgeBase.id)
            .join(KBPermission, KBPermission.knowledge_base_id == KnowledgeBase.id)
            .where(KBPermission.user_id == user.id)
            .distinct()
        ).all()
        return list(rows)

    async def chat(
        self,
        db: Session,
        user: User,
        assistant_type: str,
        payload: AssistantChatRequest,
    ) -> AssistantChatResponse:
        try:
            preset = get_assistant_preset(assistant_type)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        kb_ids = self.accessible_kb_ids(db, user)
        if not kb_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No accessible knowledge bases")

        response = await self.chat_with_preset(db=db, user=user, preset=preset, payload=payload, kb_ids=kb_ids)
        return response

    async def chat_with_preset(
        self,
        db: Session,
        user: User,
        preset: AssistantPreset,
        payload: AssistantChatRequest,
        kb_ids: list[UUID],
    ) -> AssistantChatResponse:
        use_rerank = preset.default_use_rerank if payload.use_rerank is None else payload.use_rerank
        auto_metadata_filter = (
            preset.default_auto_metadata_filter
            if payload.auto_metadata_filter is None
            else payload.auto_metadata_filter
        )
        answer_result = await self.chat_service.answer(
            db=db,
            user=user,
            message=payload.query,
            knowledge_base_ids=kb_ids,
            conversation_id=payload.conversation_id,
            metadata_filter=payload.metadata_filter,
            auto_metadata_filter=auto_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=payload.rerank_top_n or preset.default_rerank_top_n,
            top_k=payload.top_k or preset.default_top_k,
            system_prompt=preset.system_prompt,
            base_metadata_filter={} if payload.disable_preset_metadata_filter else preset.default_metadata_filter,
            include_retrieval_results=True,
        )
        (
            answer,
            citations,
            conversation,
            used_metadata_filter,
            rerank_applied,
            rerank_error,
            *optional_trace,
        ) = answer_result
        retrieved_results = optional_trace[0] if optional_trace else []
        return AssistantChatResponse(
            assistant_type=preset.assistant_type.value,
            answer=answer,
            citations=citations,
            used_metadata_filter=used_metadata_filter,
            use_rerank=use_rerank,
            rerank_applied=rerank_applied,
            rerank_error=rerank_error,
            sources=citations,
            no_answer_detected=answer.strip() == NO_EVIDENCE_ANSWER,
            conversation_id=conversation.id,
            retrieved_results=retrieved_results,
        )
