from app.db.session import SessionLocal
from app.core.tracing import ensure_trace_id, start_span
from app.models.backup_job import BackupJobType
from app.services.backup_service import BackupService
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.backup_tasks.backup_postgres")
def backup_postgres(trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.backup_postgres"):
            return str(BackupService(db).run(BackupJobType.postgres).id)


@celery_app.task(name="app.tasks.backup_tasks.backup_qdrant")
def backup_qdrant(trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.backup_qdrant"):
            return str(BackupService(db).run(BackupJobType.qdrant).id)


@celery_app.task(name="app.tasks.backup_tasks.backup_uploads")
def backup_uploads(trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.backup_uploads"):
            return str(BackupService(db).run(BackupJobType.uploads).id)


@celery_app.task(name="app.tasks.backup_tasks.backup_all")
def backup_all(trace_id: str | None = None) -> str:
    ensure_trace_id(trace_id)
    with SessionLocal() as db:
        with start_span("celery.backup_all"):
            return str(BackupService(db).run(BackupJobType.all).id)
