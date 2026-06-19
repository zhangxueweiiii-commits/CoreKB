from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import httpx
from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.index_job import IndexJob, IndexJobStatus
from app.models.audit_log import AuditLog
from app.models.backup_job import BackupJob
from app.models.alert_event import AlertEvent, AlertEventStatus
from app.models.user import User
from app.schemas.system import QueueStatusResponse
from app.services.vector_store import VectorStore
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/queue-status", response_model=QueueStatusResponse)
def queue_status(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QueueStatusResponse:
    settings = get_settings()
    redis_connected = False
    postgres_connected = False
    qdrant_connected = False
    pending_task_count: int | None = None
    active_task_count: int | None = None
    celery_available = False

    try:
        redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        redis_client.ping()
        redis_connected = True
        pending_task_count = int(redis_client.llen("celery"))
    except Exception:
        redis_connected = False
        pending_task_count = None

    try:
        db.execute(text("SELECT 1"))
        postgres_connected = True
    except Exception:
        postgres_connected = False

    try:
        import asyncio

        asyncio.run(VectorStore().client.get_collections())
        qdrant_connected = True
    except Exception:
        qdrant_connected = False

    try:
        inspector = celery_app.control.inspect(timeout=1)
        ping = inspector.ping() or {}
        celery_available = bool(ping)
        active = inspector.active() or {}
        active_task_count = sum(len(tasks) for tasks in active.values())
    except Exception:
        celery_available = False
        active_task_count = None

    failed_recent_count = int(
        db.scalar(
            select(func.count(IndexJob.id)).where(
                IndexJob.status.in_([IndexJobStatus.failed, IndexJobStatus.partial_failed]),
                IndexJob.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
        )
        or 0
    )
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    running_index_jobs = int(db.scalar(select(func.count(IndexJob.id)).where(IndexJob.status == IndexJobStatus.running)) or 0)
    pending_index_jobs = int(db.scalar(select(func.count(IndexJob.id)).where(IndexJob.status == IndexJobStatus.pending)) or 0)
    try:
        chat_today_count = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "chat.ask", AuditLog.created_at >= today)) or 0)
        search_today_count = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "search.query", AuditLog.created_at >= today)) or 0)
        document_upload_today_count = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "document.upload", AuditLog.created_at >= today)) or 0)
        recent_error_count = int(db.scalar(select(func.count(AuditLog.id)).where(AuditLog.status == "failed", AuditLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))) or 0)
    except Exception:
        chat_today_count = 0
        search_today_count = 0
        document_upload_today_count = 0
        recent_error_count = 0

    latest_backup = db.scalar(select(BackupJob).order_by(BackupJob.created_at.desc()))
    latest_alert = db.scalar(
        select(AlertEvent)
        .where(AlertEvent.status == AlertEventStatus.open)
        .order_by(AlertEvent.created_at.desc())
    )
    latest_failed_alert = latest_alert.title if latest_alert else None
    loki_status = None
    if settings.loki_enabled:
        try:
            response = httpx.get(f"{settings.loki_url.rstrip('/')}/ready", timeout=2)
            loki_status = "ok" if response.status_code < 500 else "degraded"
        except Exception:
            loki_status = "unavailable"

    return QueueStatusResponse(
        redis_connected=redis_connected,
        celery_available=celery_available,
        pending_task_count=pending_task_count,
        active_task_count=active_task_count,
        failed_recent_count=failed_recent_count,
        postgres_connected=postgres_connected,
        qdrant_connected=qdrant_connected,
        running_index_jobs=running_index_jobs,
        pending_index_jobs=pending_index_jobs,
        chat_today_count=chat_today_count,
        search_today_count=search_today_count,
        document_upload_today_count=document_upload_today_count,
        recent_error_count=recent_error_count,
        flower_url=settings.flower_url,
        latest_backup_status=latest_backup.status.value if latest_backup else None,
        latest_backup_time=latest_backup.finished_at.isoformat() if latest_backup and latest_backup.finished_at else None,
        latest_failed_alert=latest_failed_alert,
        tracing_enabled=settings.otel_enabled,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        apm_enabled=settings.apm_enabled,
        jaeger_url=settings.jaeger_url,
        loki_enabled=settings.loki_enabled,
        loki_status=loki_status,
    )
