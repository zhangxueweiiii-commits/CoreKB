from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CoreKB"
    environment: str = "local"
    api_prefix: str = "/api"
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    secret_key: str = "change-me-in-production-use-env-secret-key"
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    database_url: str = "postgresql+psycopg://corekb:corekb@localhost:5432/corekb"

    upload_dir: Path = Path("storage/uploads")
    max_upload_size_mb: int = 50

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "corekb_chunks"
    embedding_dimension: int = 1536

    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = ""
    llm_chat_model: str = "gpt-4o-mini"
    llm_embedding_model: str = "text-embedding-3-small"
    llm_timeout_seconds: int = 60
    flower_url: str = "http://localhost:5555"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    default_top_k: int = 5
    default_score_threshold: float = 0.2
    default_chunk_size: int = 800
    default_chunk_overlap: int = 100
    evaluation_kb_name: str = "CoreKB Evaluation KB"
    evaluation_fixtures_dir: Path = Path("backend/tests/evaluation/fixtures/documents")
    rerank_enabled: bool = False
    rerank_provider: str = "openai_compatible"
    rerank_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_model: str | None = None
    rerank_top_n: int = 20

    rate_limit_enabled: bool = True
    rate_limit_admin_multiplier: int = 3
    rate_limit_login_per_5m: int = 20
    rate_limit_chat_per_minute: int = 30
    rate_limit_search_per_minute: int = 60
    rate_limit_upload_per_minute: int = 10
    rate_limit_index_ops_per_10m: int = 10

    alert_enabled: bool = False
    alert_webhook_url: str | None = None
    alert_failed_job_threshold: int = 5
    alert_backup_failed_enabled: bool = True

    backup_enabled: bool = False
    backup_cron: str = "0 2 * * *"
    backup_dir: Path = Path("storage/backups")
    backup_retention_days: int = 14
    qdrant_storage_dir: Path | None = None

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "corekb-api"
    apm_enabled: bool = False
    jaeger_url: str = "http://localhost:16686"
    loki_enabled: bool = False
    loki_url: str = "http://loki:3100"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    return settings
