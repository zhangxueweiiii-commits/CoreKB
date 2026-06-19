from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.metadata_precheck import MetadataPrecheckResponse, MetadataPrecheckSummaryResponse
from app.services.metadata_normalization_precheck_service import MetadataNormalizationPrecheckService


router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/precheck", response_model=MetadataPrecheckResponse)
def metadata_precheck(
    knowledge_base_id: UUID | None = None,
    document_id: UUID | None = None,
    field_name: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    order_by: str = "document_id",
    order_direction: str = "asc",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return MetadataNormalizationPrecheckService(db).run_metadata_normalization_precheck(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            field_name=field_name,
            status=status_filter,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/precheck/summary", response_model=MetadataPrecheckSummaryResponse)
def metadata_precheck_summary(
    knowledge_base_id: UUID | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return MetadataNormalizationPrecheckService(db).get_summary(knowledge_base_id=knowledge_base_id)
