from datetime import datetime, timezone

import pytest
from fastapi import Response

from app.api.routes import health as health_routes
from app.api.routes import metrics as metrics_routes
from app.schemas.health import HealthResponse


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement):
        return None

    def scalar(self, statement):
        return 0


class FakeRedis:
    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    def ping(self):
        return True


class FakeVectorClient:
    async def get_collections(self):
        return []


class FakeVectorStore:
    def __init__(self):
        self.client = FakeVectorClient()


class FakeInspect:
    def ping(self):
        return {"worker@corekb": {"ok": "pong"}}


class FakeControl:
    def inspect(self, timeout=1):
        return FakeInspect()


class FakeCeleryApp:
    control = FakeControl()


@pytest.mark.asyncio
async def test_health_returns_dependency_status(monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(health_routes, "Redis", FakeRedis)
    monkeypatch.setattr(health_routes, "VectorStore", FakeVectorStore)
    monkeypatch.setattr(health_routes, "celery_app", FakeCeleryApp())

    result = await health_routes.health()

    assert result.status == "ok"
    assert result.api is True
    assert result.postgres is True
    assert result.redis is True
    assert result.qdrant is True
    assert result.celery is True


def test_health_live_available() -> None:
    assert health_routes.live() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_available(monkeypatch) -> None:
    async def fake_health():
        return HealthResponse(
            status="ok",
            api=True,
            postgres=True,
            redis=True,
            qdrant=True,
            celery=True,
            timestamp=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(health_routes, "_health", fake_health)
    response = Response()

    result = await health_routes.ready(response)

    assert response.status_code == 200
    assert result.status == "ok"


def test_metrics_returns_prometheus_format(monkeypatch) -> None:
    monkeypatch.setattr(metrics_routes, "SessionLocal", lambda: FakeSession())

    response = metrics_routes.metrics()
    body = response.body.decode("utf-8")

    assert response.media_type.startswith("text/plain")
    assert "# HELP" in body
    assert "active_index_jobs" in body
