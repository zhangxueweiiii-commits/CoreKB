import logging
from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentChunk
from app.models.retrieval_log import RetrievalLog
from app.models.user import User
from app.services.embedding_service import EmbeddingService
from app.services.query_metadata_extractor import sanitize_metadata_filter
from app.services.rerank_service import RerankService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_text: str
    filename: str
    page_number: int | None
    score: float
    document_id: UUID
    chunk_id: UUID
    section_title: str | None = None
    metadata: dict | None = None
    vector_score: float | None = None
    rerank_score: float | None = None
    final_score: float | None = None


@dataclass(frozen=True)
class RetrievalResultSet:
    results: list[RetrievedChunk]
    use_rerank: bool = False
    rerank_applied: bool = False
    rerank_error: str | None = None


class RetrievalService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.rerank_service = RerankService()

    async def search(
        self,
        db: Session,
        user: User,
        query: str,
        knowledge_base_ids: list[UUID],
        top_k: int | None = None,
        score_threshold: float | None = None,
        metadata_filter: dict | None = None,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
    ) -> list[RetrievedChunk]:
        return (
            await self.search_with_options(
                db=db,
                user=user,
                query=query,
                knowledge_base_ids=knowledge_base_ids,
                top_k=top_k,
                score_threshold=score_threshold,
                metadata_filter=metadata_filter,
                use_rerank=use_rerank,
                rerank_top_n=rerank_top_n,
            )
        ).results

    async def search_with_options(
        self,
        db: Session,
        user: User,
        query: str,
        knowledge_base_ids: list[UUID],
        top_k: int | None = None,
        score_threshold: float | None = None,
        metadata_filter: dict | None = None,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
    ) -> RetrievalResultSet:
        final_top_k = top_k or self.settings.default_top_k
        candidate_limit = final_top_k
        if use_rerank:
            candidate_limit = max(final_top_k, rerank_top_n or self.settings.rerank_top_n)
        vector = await self.embedding_service.embed_query(query)
        kb_ids = [str(kb_id) for kb_id in knowledge_base_ids]
        sanitized_metadata_filter = sanitize_metadata_filter(metadata_filter)
        hits = await self.vector_store.search(
            vector,
            kb_ids,
            candidate_limit,
            self.settings.default_score_threshold if score_threshold is None else score_threshold,
            sanitized_metadata_filter,
        )
        chunk_ids = [UUID(hit.payload["chunk_id"]) for hit in hits if hit.payload and hit.payload.get("chunk_id")]
        chunks = {
            chunk.id: chunk
            for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))).all()
        }
        results: list[RetrievedChunk] = []
        for hit in hits:
            if not hit.payload or not hit.payload.get("chunk_id"):
                continue
            chunk_id = UUID(hit.payload["chunk_id"])
            chunk = chunks.get(chunk_id)
            if not chunk:
                continue
            results.append(
                RetrievedChunk(
                    chunk_text=chunk.chunk_text,
                    filename=str(hit.payload.get("filename") or ""),
                    page_number=hit.payload.get("page_number"),
                    score=float(hit.score),
                    document_id=UUID(hit.payload["document_id"]),
                    chunk_id=chunk_id,
                    section_title=hit.payload.get("section_title"),
                    metadata=chunk.meta,
                    vector_score=float(hit.score),
                    final_score=float(hit.score),
                )
            )

        rerank_applied = False
        rerank_error = None
        if use_rerank and results:
            try:
                results = await self.rerank_service.rerank_results(
                    query,
                    results,
                    rerank_top_n or self.settings.rerank_top_n,
                )
                rerank_applied = True
            except Exception as exc:
                rerank_error = str(exc)
                logger.warning("Rerank failed; falling back to vector results: %s", exc)
                results = [replace(result, final_score=result.vector_score) for result in results]
        results = results[:final_top_k]

        db.add(
            RetrievalLog(
                user_id=user.id,
                query=query,
                knowledge_base_ids=kb_ids,
                retrieved_chunk_ids=[str(item.chunk_id) for item in results],
                scores=[item.score for item in results],
            )
        )
        db.commit()
        return RetrievalResultSet(
            results=results,
            use_rerank=use_rerank,
            rerank_applied=rerank_applied,
            rerank_error=rerank_error,
        )
