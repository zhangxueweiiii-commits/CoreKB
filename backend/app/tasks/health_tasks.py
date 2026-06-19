from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.health_tasks.celery_health_check")
def celery_health_check(value: str = "ok") -> str:
    return value
