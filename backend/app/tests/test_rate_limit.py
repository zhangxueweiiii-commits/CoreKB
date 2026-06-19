from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.security import create_access_token
from app.middleware.rate_limit import RateLimitMiddleware


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> None:
        return None


def make_settings(**overrides):
    real = get_settings()
    data = {
        "api_prefix": "/api",
        "rate_limit_enabled": True,
        "rate_limit_login_per_5m": 1,
        "rate_limit_chat_per_minute": 1,
        "rate_limit_search_per_minute": 60,
        "rate_limit_upload_per_minute": 10,
        "rate_limit_index_ops_per_10m": 10,
        "rate_limit_admin_multiplier": 2,
        "secret_key": real.secret_key,
        "algorithm": real.algorithm,
        "redis_url": real.redis_url,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_request(path: str, *, token: str | None = None, ip: str = "127.0.0.1") -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers,
            "client": (ip, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


async def ok_response(request):
    return JSONResponse({"ok": True})


def make_middleware(settings):
    middleware = RateLimitMiddleware(lambda scope, receive, send: None)
    middleware.settings = settings
    middleware.redis = FakeRedis()
    return middleware


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429() -> None:
    middleware = make_middleware(make_settings(rate_limit_login_per_5m=1))

    first = await middleware.dispatch(make_request("/api/auth/login", ip="10.0.0.1"), ok_response)
    second = await middleware.dispatch(make_request("/api/auth/login", ip="10.0.0.1"), ok_response)

    assert first.status_code == 200
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_chat_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setattr(RateLimitMiddleware, "_is_admin", staticmethod(lambda user_id: False))
    middleware = make_middleware(make_settings(rate_limit_chat_per_minute=1))
    token = create_access_token("11111111-1111-1111-1111-111111111111")

    first = await middleware.dispatch(make_request("/api/chat", token=token), ok_response)
    second = await middleware.dispatch(make_request("/api/chat", token=token), ok_response)

    assert first.status_code == 200
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_can_be_disabled_in_tests() -> None:
    middleware = make_middleware(make_settings(rate_limit_enabled=False, rate_limit_login_per_5m=1))

    first = await middleware.dispatch(make_request("/api/auth/login", ip="10.0.0.2"), ok_response)
    second = await middleware.dispatch(make_request("/api/auth/login", ip="10.0.0.2"), ok_response)

    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_is_isolated_by_user(monkeypatch) -> None:
    monkeypatch.setattr(RateLimitMiddleware, "_is_admin", staticmethod(lambda user_id: False))
    middleware = make_middleware(make_settings(rate_limit_chat_per_minute=1))
    first_user = create_access_token("11111111-1111-1111-1111-111111111111")
    second_user = create_access_token("22222222-2222-2222-2222-222222222222")

    await middleware.dispatch(make_request("/api/chat", token=first_user), ok_response)
    first_user_second = await middleware.dispatch(make_request("/api/chat", token=first_user), ok_response)
    second_user_first = await middleware.dispatch(make_request("/api/chat", token=second_user), ok_response)

    assert first_user_second.status_code == 429
    assert second_user_first.status_code == 200
