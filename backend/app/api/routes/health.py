from datetime import datetime, timezone

from fastapi import APIRouter, Response, status
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.schemas.health import HealthResponse
from app.services.alert_service import AlertService
from app.services.vector_store import VectorStore
from app.tasks.celery_app import celery_app

router = APIRouter(tags=["health"])


async def _health() -> HealthResponse:
    settings = get_settings()
    postgres = False
    redis = False
    qdrant = False
    celery = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            postgres = True
    except Exception:
        postgres = False
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
        redis = True
    except Exception:
        redis = False
    try:
        await VectorStore().client.get_collections()
        qdrant = True
    except Exception:
        qdrant = False
    try:
        celery = bool(celery_app.control.inspect(timeout=1).ping() or {})
    except Exception:
        celery = False
    ok = postgres and redis and qdrant
    if not postgres:
        AlertService().health_unavailable("postgres")
    if not redis:
        AlertService().health_unavailable("redis")
    if not qdrant:
        AlertService().health_unavailable("qdrant")
    return HealthResponse(
        status="ok" if ok else "degraded",
        api=True,
        postgres=postgres,
        redis=redis,
        qdrant=qdrant,
        celery=celery,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return await _health()


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=HealthResponse)
async def ready(response: Response) -> HealthResponse:
    result = await _health()
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
