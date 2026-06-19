from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select

from app.core.metrics import ACTIVE_INDEX_JOBS, FAILED_INDEX_JOBS_TOTAL
from app.db.session import SessionLocal
from app.models.index_job import IndexJob, IndexJobStatus

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics() -> Response:
    with SessionLocal() as db:
        active = int(
            db.scalar(
                select(func.count(IndexJob.id)).where(
                    IndexJob.status.in_([IndexJobStatus.pending, IndexJobStatus.running, IndexJobStatus.paused])
                )
            )
            or 0
        )
        failed = int(
            db.scalar(
                select(func.count(IndexJob.id)).where(
                    IndexJob.status.in_([IndexJobStatus.failed, IndexJobStatus.partial_failed])
                )
            )
            or 0
        )
    ACTIVE_INDEX_JOBS.set(active)
    FAILED_INDEX_JOBS_TOTAL.set(failed)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
