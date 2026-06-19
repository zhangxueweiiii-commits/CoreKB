from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_kb_or_404
from app.db.session import get_db
from app.models.document import Document
from app.models.index_job import IndexJob, IndexJobItem, IndexJobItemStatus, IndexJobStatus, IndexJobType
from app.models.user import User, UserRole
from app.core.metrics import INDEX_JOBS_TOTAL
from app.schemas.index_job import IndexJobActionResponse, IndexJobDetail, IndexJobItemRead, IndexJobStats, IndexJobSummary
from app.services.audit_service import AuditService
from app.services.index_job_service import IndexJobService
from app.services.permission_service import PermissionService
from app.tasks.document_tasks import enqueue_reindex_job

router = APIRouter(prefix="/index-jobs", tags=["index jobs"])


def _accessible_kb_ids(db: Session, user: User) -> list[UUID] | None:
    if user.role == UserRole.admin:
        return None
    rows = db.execute(select(IndexJob.knowledge_base_id).distinct()).scalars().all()
    return PermissionService(db).filter_accessible_kb_ids(user, list(rows))


@router.get("/stats", response_model=IndexJobStats)
def index_job_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobStats:
    kb_ids = _accessible_kb_ids(db, current_user)
    stats = IndexJobService(db).stats_for_kb_ids(kb_ids)
    return IndexJobStats(**stats)


@router.get("", response_model=list[IndexJobSummary])
def list_index_jobs(
    status_filter: IndexJobStatus | None = Query(default=None, alias="status"),
    job_type: IndexJobType | None = None,
    knowledge_base_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IndexJob]:
    stmt = select(IndexJob).order_by(IndexJob.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(IndexJob.status == status_filter)
    if job_type:
        stmt = stmt.where(IndexJob.job_type == job_type)
    if knowledge_base_id:
        get_kb_or_404(db, knowledge_base_id)
        if not PermissionService(db).can_view_kb(current_user, knowledge_base_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to knowledge base")
        stmt = stmt.where(IndexJob.knowledge_base_id == knowledge_base_id)
    elif current_user.role != UserRole.admin:
        kb_ids = _accessible_kb_ids(db, current_user) or []
        if not kb_ids:
            return []
        stmt = stmt.where(IndexJob.knowledge_base_id.in_(kb_ids))
    return list(db.scalars(stmt).all())


@router.get("/{job_id}", response_model=IndexJobDetail)
def get_index_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobDetail:
    job = db.get(IndexJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    if current_user.role != UserRole.admin and not PermissionService(db).can_view_kb(
        current_user, job.knowledge_base_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to index job")
    rows = db.execute(
        select(IndexJobItem, Document.filename)
        .join(Document, Document.id == IndexJobItem.document_id)
        .where(IndexJobItem.job_id == job.id)
        .order_by(IndexJobItem.created_at.asc())
    ).all()
    summary = IndexJobDetail.model_validate(job)
    return summary.model_copy(
        update={
            "items": [
                IndexJobItemRead(
                    id=item.id,
                    document_id=item.document_id,
                    filename=filename,
                    status=item.status,
                    error_message=item.error_message,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                )
                for item, filename in rows
            ]
        }
    )


def _require_job_editor(db: Session, user: User, job: IndexJob) -> None:
    if user.role == UserRole.admin:
        return
    if not PermissionService(db).can_edit_kb(user, job.knowledge_base_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No edit access to index job")


@router.post("/{job_id}/retry-failed", response_model=IndexJobActionResponse)
def retry_failed_items(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobActionResponse:
    job = db.get(IndexJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    _require_job_editor(db, current_user, job)
    failed_items = list(
        db.scalars(
            select(IndexJobItem).where(
                IndexJobItem.job_id == job.id,
                IndexJobItem.status == IndexJobItemStatus.failed,
            )
        ).all()
    )
    if not failed_items:
        return IndexJobActionResponse(message="No failed items to retry", job=None)
    new_job = IndexJobService(db).create_retry_failed_job(job, current_user, failed_items)
    enqueue_reindex_job(new_job.id)
    INDEX_JOBS_TOTAL.labels(new_job.job_type.value).inc()
    AuditService(db).record(
        actor=current_user,
        action="index_job.retry_failed",
        resource_type="index_job",
        resource_id=new_job.id,
        knowledge_base_id=new_job.knowledge_base_id,
        status="success",
        metadata={"source_job_id": str(job.id), "failed_count": len(failed_items)},
    )
    return IndexJobActionResponse(message="Retry job submitted", job=new_job)


@router.post("/{job_id}/cancel", response_model=IndexJobActionResponse)
def cancel_index_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobActionResponse:
    job = db.get(IndexJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    _require_job_editor(db, current_user, job)
    if job.status not in {IndexJobStatus.pending, IndexJobStatus.running, IndexJobStatus.paused}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending, running, or paused jobs can be cancelled")
    job.status = IndexJobStatus.cancelled
    pending_items = list(
        db.scalars(
            select(IndexJobItem).where(
                IndexJobItem.job_id == job.id,
                IndexJobItem.status == IndexJobItemStatus.pending,
            )
        ).all()
    )
    for item in pending_items:
        item.status = IndexJobItemStatus.cancelled
        item.finished_at = datetime.now(timezone.utc)
    IndexJobService(db).recompute_counts(job)
    db.commit()
    db.refresh(job)
    AuditService(db).record(
        actor=current_user,
        action="index_job.cancel",
        resource_type="index_job",
        resource_id=job.id,
        knowledge_base_id=job.knowledge_base_id,
        status="success",
    )
    return IndexJobActionResponse(message="Job cancelled", job=job)


@router.post("/{job_id}/pause", response_model=IndexJobActionResponse)
def pause_index_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobActionResponse:
    job = db.get(IndexJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    _require_job_editor(db, current_user, job)
    if job.status not in {IndexJobStatus.pending, IndexJobStatus.running}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending or running jobs can be paused")
    job.status = IndexJobStatus.paused
    IndexJobService(db).recompute_counts(job)
    db.commit()
    db.refresh(job)
    AuditService(db).record(
        actor=current_user,
        action="index_job.pause",
        resource_type="index_job",
        resource_id=job.id,
        knowledge_base_id=job.knowledge_base_id,
        status="success",
    )
    return IndexJobActionResponse(message="Job paused", job=job)


@router.post("/{job_id}/resume", response_model=IndexJobActionResponse)
def resume_index_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobActionResponse:
    job = db.get(IndexJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    _require_job_editor(db, current_user, job)
    if job.status != IndexJobStatus.paused:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only paused jobs can be resumed")
    job.status = IndexJobStatus.pending
    job.finished_at = None
    IndexJobService(db).recompute_counts(job)
    db.commit()
    db.refresh(job)
    enqueue_reindex_job(job.id)
    AuditService(db).record(
        actor=current_user,
        action="index_job.resume",
        resource_type="index_job",
        resource_id=job.id,
        knowledge_base_id=job.knowledge_base_id,
        status="success",
    )
    return IndexJobActionResponse(message="Job resumed", job=job)
