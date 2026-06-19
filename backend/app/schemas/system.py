from pydantic import BaseModel


class QueueStatusResponse(BaseModel):
    redis_connected: bool
    celery_available: bool
    pending_task_count: int | None = None
    active_task_count: int | None = None
    failed_recent_count: int | None = None
    api_healthy: bool = True
    postgres_connected: bool | None = None
    qdrant_connected: bool | None = None
    running_index_jobs: int = 0
    pending_index_jobs: int = 0
    chat_today_count: int = 0
    search_today_count: int = 0
    document_upload_today_count: int = 0
    recent_error_count: int = 0
    flower_url: str | None = None
    latest_backup_status: str | None = None
    latest_backup_time: str | None = None
    latest_failed_alert: str | None = None
    tracing_enabled: bool = False
    otlp_endpoint: str | None = None
    apm_enabled: bool = False
    jaeger_url: str | None = None
    loki_enabled: bool = False
    loki_status: str | None = None
