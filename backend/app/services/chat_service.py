from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.llm_service import LLMService
from app.services.query_metadata_extractor import extract_metadata_from_query, sanitize_metadata_filter
from app.services.retrieval_service import RetrievedChunk, RetrievalService


NO_EVIDENCE_ANSWER = "当前知识库未找到可靠依据。"


def resolve_chat_metadata_filter(
    query: str,
    explicit_filter: dict | None = None,
    auto_metadata_filter: bool = False,
    base_filter: dict | None = None,
) -> dict:
    auto_filter = extract_metadata_from_query(query) if auto_metadata_filter else {}
    return {
        **sanitize_metadata_filter(base_filter),
        **auto_filter,
        **sanitize_metadata_filter(explicit_filter),
    }


class ChatService:
    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()
        self.llm_service = LLMService()

    async def answer(
        self,
        db: Session,
        user: User,
        message: str,
        knowledge_base_ids: list[UUID],
        conversation_id: UUID | None,
        metadata_filter: dict | None = None,
        auto_metadata_filter: bool = False,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
        top_k: int = 5,
        system_prompt: str | None = None,
        base_metadata_filter: dict | None = None,
        include_retrieval_results: bool = False,
    ) -> tuple:
        conversation = self._get_or_create_conversation(
            db, user, message, knowledge_base_ids, conversation_id
        )
        used_metadata_filter = resolve_chat_metadata_filter(
            message,
            metadata_filter,
            auto_metadata_filter,
            base_metadata_filter,
        )
        result_set = await self.retrieval_service.search_with_options(
            db=db,
            user=user,
            query=message,
            knowledge_base_ids=knowledge_base_ids,
            top_k=top_k,
            score_threshold=None,
            metadata_filter=used_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
        )
        results = result_set.results

        citations = self.citations(results)
        if not results:
            answer = NO_EVIDENCE_ANSWER
        else:
            answer = await self.llm_service.chat(self.build_messages(message, results, system_prompt))
            if not answer:
                answer = NO_EVIDENCE_ANSWER

        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=message,
                citations=[],
                knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids],
            )
        )
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                citations=citations if answer != NO_EVIDENCE_ANSWER else [],
                knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids],
            )
        )
        db.commit()
        db.refresh(conversation)
        return (
            answer,
            (citations if answer != NO_EVIDENCE_ANSWER else []),
            conversation,
            used_metadata_filter,
            result_set.rerank_applied,
            result_set.rerank_error,
            self.retrieval_snapshot(results) if include_retrieval_results else [],
        )

    def _get_or_create_conversation(
        self,
        db: Session,
        user: User,
        message: str,
        knowledge_base_ids: list[UUID],
        conversation_id: UUID | None,
    ) -> Conversation:
        if conversation_id:
            conversation = db.get(
                Conversation,
                conversation_id,
                options=[selectinload(Conversation.messages)],
            )
            if not conversation or conversation.user_id != user.id:
                raise ValueError("Conversation not found")
            return conversation
        conversation = Conversation(
            user_id=user.id,
            title=message[:80],
            knowledge_base_ids=[str(kb_id) for kb_id in knowledge_base_ids],
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def build_messages(
        self,
        message: str,
        results: list[RetrievedChunk],
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        context_blocks = []
        for index, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            if metadata.get("source_type") == "table":
                source = (
                    f"file={result.filename}, sheet={metadata.get('sheet_name')}, "
                    f"rows={metadata.get('row_start')}-{metadata.get('row_end')}, chunk_id={result.chunk_id}"
                )
            else:
                page = f"p.{result.page_number}" if result.page_number else "no page"
                section = f", section={result.section_title}" if result.section_title else ""
                source = f"file={result.filename}, page={page}{section}, chunk_id={result.chunk_id}"
            context_blocks.append(f"[{index}] {source}\n{result.chunk_text}")
        system = system_prompt or (
            "你是 CoreKB 企业知识库问答助手。只能依据提供的知识库片段回答。"
            "如果片段中没有可靠依据，必须只回答：当前知识库未找到可靠依据。"
            "回答要简洁，并尽量指出依据来自哪些文件、页码、Sheet 或行范围。"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "知识库片段：\n\n" + "\n\n".join(context_blocks)},
            {"role": "user", "content": message},
        ]

    def citation(self, result: RetrievedChunk) -> dict:
        metadata = result.metadata or {}
        return {
            "filename": result.filename,
            "page_number": result.page_number,
            "section_title": result.section_title,
            "sheet_name": metadata.get("sheet_name"),
            "row_start": metadata.get("row_start"),
            "row_end": metadata.get("row_end"),
            "chunk_id": str(result.chunk_id),
            "quote": result.chunk_text[:300],
        }

    def citations(self, results: list[RetrievedChunk]) -> list[dict]:
        return [self.citation(result) for result in results]

    def retrieval_snapshot(self, results: list[RetrievedChunk]) -> list[dict]:
        return [
            {
                "rank": index,
                "document_id": str(result.document_id),
                "document_name": result.filename,
                "chunk_id": str(result.chunk_id),
                "chunk_excerpt": result.chunk_text[:1200],
                "chunk_metadata": result.metadata or {},
                "vector_score": result.vector_score,
                "rerank_score": result.rerank_score,
                "final_score": result.final_score,
                "citation": self.citation(result),
            }
            for index, result in enumerate(results, start=1)
        ]
