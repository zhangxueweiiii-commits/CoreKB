from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.index_job import (
    IndexJob,
    IndexJobItem,
    IndexJobItemStatus,
    IndexJobStatus,
    IndexJobType,
)
from app.models.user import User


class IndexJobService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_document_job(self, document: Document, user: User | None) -> IndexJob:
        job = IndexJob(
            job_type=IndexJobType.document_index,
            status=IndexJobStatus.pending,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            created_by=user.id if user else None,
            total_count=1,
            success_count=0,
            failed_count=0,
            pending_count=1,
            meta={},
        )
        self.db.add(job)
        self.db.flush()
        self.db.add(IndexJobItem(job_id=job.id, document_id=document.id, status=IndexJobItemStatus.pending))
        self.db.commit()
        self.db.refresh(job)
        return job

    def create_kb_reindex_job(
        self,
        knowledge_base_id: UUID,
        documents: list[Document],
        user: User,
        force: bool,
    ) -> IndexJob:
        job = IndexJob(
            job_type=IndexJobType.kb_reindex,
            status=IndexJobStatus.pending,
            knowledge_base_id=knowledge_base_id,
            created_by=user.id,
            total_count=len(documents),
            success_count=0,
            failed_count=0,
            pending_count=len(documents),
            meta={"force": force},
        )
        self.db.add(job)
        self.db.flush()
        for document in documents:
            self.db.add(
                IndexJobItem(
                    job_id=job.id,
                    document_id=document.id,
                    status=IndexJobItemStatus.pending,
                )
            )
        self.db.commit()
        self.db.refresh(job)
        return job

    def create_retry_failed_job(self, source_job: IndexJob, user: User, failed_items: list[IndexJobItem]) -> IndexJob:
        job = IndexJob(
            job_type=IndexJobType.retry_failed,
            status=IndexJobStatus.pending,
            knowledge_base_id=source_job.knowledge_base_id,
            created_by=user.id,
            total_count=len(failed_items),
            success_count=0,
            failed_count=0,
            pending_count=len(failed_items),
            meta={"source_job_id": str(source_job.id)},
        )
        self.db.add(job)
        self.db.flush()
        for item in failed_items:
            self.db.add(
                IndexJobItem(
                    job_id=job.id,
                    document_id=item.document_id,
                    status=IndexJobItemStatus.pending,
                )
            )
        self.db.commit()
        self.db.refresh(job)
        return job

    def recompute_counts(self, job: IndexJob) -> None:
        rows = self.db.execute(
            select(IndexJobItem.status, func.count(IndexJobItem.id))
            .where(IndexJobItem.job_id == job.id)
            .group_by(IndexJobItem.status)
        ).all()
        counts = {status: int(count) for status, count in rows}
        job.success_count = counts.get(IndexJobItemStatus.completed, 0)
        job.failed_count = counts.get(IndexJobItemStatus.failed, 0)
        job.pending_count = (
            counts.get(IndexJobItemStatus.pending, 0)
            + counts.get(IndexJobItemStatus.running, 0)
        )

    def finalize_job(self, job: IndexJob) -> None:
        self.recompute_counts(job)
        job.pending_count = 0
        if job.total_count == 0:
            job.status = IndexJobStatus.completed
        elif job.success_count == job.total_count:
            job.status = IndexJobStatus.completed
        elif job.failed_count == job.total_count:
            job.status = IndexJobStatus.failed
        elif job.failed_count > 0:
            job.status = IndexJobStatus.partial_failed
        else:
            job.status = IndexJobStatus.completed
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()

    def stats_for_kb_ids(self, kb_ids: list[UUID] | None = None) -> dict:
        stmt = select(IndexJob.status, func.count(IndexJob.id)).group_by(IndexJob.status)
        if kb_ids is not None:
            stmt = stmt.where(IndexJob.knowledge_base_id.in_(kb_ids))
        rows = self.db.execute(stmt).all()
        counts = {status: int(count) for status, count in rows}
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_stmt = select(func.count(IndexJob.id)).where(
            IndexJob.status.in_([IndexJobStatus.failed, IndexJobStatus.partial_failed]),
            IndexJob.created_at >= since,
        )
        latest_stmt = (
            select(IndexJob)
            .where(IndexJob.status.in_([IndexJobStatus.failed, IndexJobStatus.partial_failed]))
            .order_by(IndexJob.created_at.desc())
            .limit(5)
        )
        if kb_ids is not None:
            failed_stmt = failed_stmt.where(IndexJob.knowledge_base_id.in_(kb_ids))
            latest_stmt = latest_stmt.where(IndexJob.knowledge_base_id.in_(kb_ids))
        return {
            "running_count": counts.get(IndexJobStatus.running, 0),
            "pending_count": counts.get(IndexJobStatus.pending, 0),
            "completed_count": counts.get(IndexJobStatus.completed, 0),
            "partial_failed_count": counts.get(IndexJobStatus.partial_failed, 0),
            "failed_count": counts.get(IndexJobStatus.failed, 0),
            "failed_recent_count": int(self.db.scalar(failed_stmt) or 0),
            "latest_failed_jobs": list(self.db.scalars(latest_stmt).all()),
        }
