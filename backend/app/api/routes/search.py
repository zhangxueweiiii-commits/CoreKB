from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.core.metrics import SEARCH_REQUESTS_TOTAL
from app.core.tracing import start_span
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.services.query_metadata_extractor import sanitize_metadata_filter
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    accessible_kb_ids = PermissionService(db).filter_accessible_kb_ids(
        current_user, payload.knowledge_base_ids
    )
    if not accessible_kb_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No accessible knowledge bases")
    metadata_filter = sanitize_metadata_filter(payload.metadata_filter)
    try:
        with start_span("search.query", kb_count=len(accessible_kb_ids), top_k=payload.top_k):
            result_set = await RetrievalService().search_with_options(
                db=db,
                user=current_user,
                query=payload.query,
                knowledge_base_ids=accessible_kb_ids,
                top_k=payload.top_k,
                score_threshold=payload.score_threshold,
                metadata_filter=metadata_filter,
                use_rerank=payload.use_rerank,
                rerank_top_n=payload.rerank_top_n,
            )
            results = result_set.results
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    SEARCH_REQUESTS_TOTAL.inc()
    AuditService(db).record(
        actor=current_user,
        action="search.query",
        resource_type="search",
        status="success",
        metadata={
            "query_preview": payload.query[:200],
            "knowledge_base_ids": [str(kb_id) for kb_id in accessible_kb_ids],
            "result_count": len(results),
            "metadata_filter": metadata_filter,
            "use_rerank": payload.use_rerank,
            "rerank_applied": result_set.rerank_applied,
            "rerank_error": result_set.rerank_error,
        },
    )
    return SearchResponse(
        results=[
            SearchResult(
                chunk_text=item.chunk_text,
                filename=item.filename,
                page_number=item.page_number,
                score=item.score,
                vector_score=item.vector_score,
                rerank_score=item.rerank_score,
                final_score=item.final_score,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                section_title=item.section_title,
                sheet_name=(item.metadata or {}).get("sheet_name"),
                row_start=(item.metadata or {}).get("row_start"),
                row_end=(item.metadata or {}).get("row_end"),
                metadata=item.metadata or {},
            )
            for item in results
        ],
        use_rerank=payload.use_rerank,
        rerank_applied=result_set.rerank_applied,
        rerank_error=result_set.rerank_error,
    )
