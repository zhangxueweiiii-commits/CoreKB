from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import setup_tracing


configure_logging()
setup_tracing()
settings = get_settings()


def _backup_crontab():
    minute, hour, day_of_month, month_of_year, day_of_week = settings.backup_cron.split()
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


celery_app = Celery(
    "corekb",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.document_tasks", "app.tasks.health_tasks", "app.tasks.backup_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)

if settings.backup_enabled:
    celery_app.conf.beat_schedule = {
        "corekb-backup-all": {
            "task": "app.tasks.backup_tasks.backup_all",
            "schedule": _backup_crontab(),
        }
    }
