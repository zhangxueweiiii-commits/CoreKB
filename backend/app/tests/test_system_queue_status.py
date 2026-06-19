from app.api.routes.system import queue_status


def test_queue_status_returns_null_metrics_when_unavailable(monkeypatch, db_session) -> None:
    class BrokenRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            raise ConnectionError("redis down")

    class BrokenInspect:
        def ping(self):
            raise RuntimeError("celery down")

    class BrokenControl:
        def inspect(self, timeout=1):
            return BrokenInspect()

    monkeypatch.setattr("app.api.routes.system.Redis", BrokenRedis)
    monkeypatch.setattr("app.api.routes.system.celery_app.control", BrokenControl())

    status = queue_status(db=db_session)

    assert status.redis_connected is False
    assert status.celery_available is False
    assert status.pending_task_count is None
    assert status.active_task_count is None
    assert status.failed_recent_count == 0
