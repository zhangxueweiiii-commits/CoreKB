import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.tracing import ensure_trace_id, start_span
from app.db.session import SessionLocal
from app.core.metrics import INDEX_JOB_FAILURES_TOTAL
from app.models.document import Document, DocumentStatus
from app.models.index_job import IndexJob, IndexJobItem, IndexJobItemStatus, IndexJobStatus
from app.services.alert_service import AlertService
from app.services.document_ingestion import DocumentIngestionService
from app.services.index_job_service import IndexJobService
from app.tasks.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.document_tasks.process_document")
def process_document(document_id: str, trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.process_document", document_id=document_id):
            document = db.get(Document, UUID(document_id))
            if not document:
                logger.warning("Document %s not found for indexing", document_id)
                return document_id
            try:
                asyncio.run(DocumentIngestionService().process(db, document))
            except Exception as exc:
                logger.exception("Document indexing failed: %s", document_id)
                db.rollback()
                document.status = DocumentStatus.failed
                document.error_message = str(exc)[:2000]
                db.add(document)
                db.commit()
    return document_id


def enqueue_document_indexing(document_id: UUID) -> None:
    process_document.delay(str(document_id), ensure_trace_id())


@celery_app.task(name="app.tasks.document_tasks.process_reindex_job")
def process_reindex_job(job_id: str, trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.process_reindex_job", job_id=job_id):
            job = db.get(IndexJob, UUID(job_id))
            if not job:
                logger.warning("Index job %s not found", job_id)
                return job_id

            return _process_reindex_job(db, job, job_id)


def _process_reindex_job(db, job: IndexJob, job_id: str) -> str:
    service = IndexJobService(db)
    if job.status in {IndexJobStatus.cancelled, IndexJobStatus.paused}:
        return job_id
    job.status = IndexJobStatus.running
    job.started_at = job.started_at or datetime.now(timezone.utc)
    db.commit()

    items = list(
        db.query(IndexJobItem)
        .filter(IndexJobItem.job_id == job.id)
        .order_by(IndexJobItem.created_at.asc())
        .all()
    )
    ingestion = DocumentIngestionService()
    for item in items:
        db.refresh(job)
        if job.status == IndexJobStatus.cancelled:
            if item.status == IndexJobItemStatus.pending:
                item.status = IndexJobItemStatus.cancelled
                item.finished_at = datetime.now(timezone.utc)
                service.recompute_counts(job)
                db.commit()
            continue
        if job.status == IndexJobStatus.paused:
            service.recompute_counts(job)
            db.commit()
            break
        if item.status == IndexJobItemStatus.completed:
            continue
        item.status = IndexJobItemStatus.running
        item.started_at = datetime.now(timezone.utc)
        item.error_message = None
        service.recompute_counts(job)
        db.commit()

        document = db.get(Document, item.document_id)
        if not document:
            item.status = IndexJobItemStatus.skipped
            item.error_message = "Document not found"
            item.finished_at = datetime.now(timezone.utc)
            service.recompute_counts(job)
            db.commit()
            continue

        try:
            result = asyncio.run(ingestion.process(db, document))
            if result.status == DocumentStatus.indexed:
                item.status = IndexJobItemStatus.completed
                item.error_message = None
            else:
                item.status = IndexJobItemStatus.failed
                item.error_message = result.error_message or "Document indexing failed"
        except Exception as exc:
            logger.exception("Index job item failed: job=%s document=%s", job.id, item.document_id)
            db.rollback()
            document = db.get(Document, item.document_id)
            item = db.get(IndexJobItem, item.id)
            if document:
                document.status = DocumentStatus.failed
                document.error_message = str(exc)[:2000]
                db.add(document)
            item.status = IndexJobItemStatus.failed
            item.error_message = str(exc)[:2000]
            INDEX_JOB_FAILURES_TOTAL.inc()
        finally:
            item.finished_at = datetime.now(timezone.utc)
            service.recompute_counts(job)
            db.commit()

    db.refresh(job)
    if job.status not in {IndexJobStatus.cancelled, IndexJobStatus.paused}:
        service.finalize_job(job)
        db.refresh(job)
        if job.status in {IndexJobStatus.failed, IndexJobStatus.partial_failed}:
            alert_service = AlertService(db)
            alert_service.index_job_failed(job.id, f"Index job ended with status {job.status.value}")
            recent_failed = int(
                db.scalar(
                    select(func.count(IndexJob.id)).where(
                        IndexJob.status.in_([IndexJobStatus.failed, IndexJobStatus.partial_failed])
                    )
                )
                or 0
            )
            if recent_failed >= get_settings().alert_failed_job_threshold:
                alert_service.failed_job_threshold_exceeded(recent_failed)
    else:
        service.recompute_counts(job)
        if job.status == IndexJobStatus.cancelled:
            job.finished_at = datetime.now(timezone.utc)
        db.commit()
    return job_id


def enqueue_reindex_job(job_id: UUID) -> None:
    process_reindex_job.delay(str(job_id), ensure_trace_id())
