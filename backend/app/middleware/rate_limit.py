import hashlib
import time
from dataclasses import dataclass
from uuid import UUID

import jwt
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.redis: Redis | None = None

    async def dispatch(self, request: Request, call_next):
        if not self.settings.rate_limit_enabled:
            return await call_next(request)
        rule = self._match_rule(request)
        if not rule:
            return await call_next(request)
        key_identity, is_admin = self._identity(request)
        limit = rule.limit * (self.settings.rate_limit_admin_multiplier if is_admin else 1)
        if not self._allow(rule, key_identity, limit):
            return JSONResponse(
                {"detail": f"Rate limit exceeded for {rule.name}"},
                status_code=429,
                headers={"Retry-After": str(rule.window_seconds)},
            )
        return await call_next(request)

    def _match_rule(self, request: Request) -> RateLimitRule | None:
        path = request.url.path
        method = request.method.upper()
        prefix = self.settings.api_prefix.rstrip("/")
        if method == "POST" and path == f"{prefix}/auth/login":
            return RateLimitRule("login", self.settings.rate_limit_login_per_5m, 300)
        if method == "POST" and path in {f"{prefix}/chat", f"{prefix}/chat/stream"}:
            return RateLimitRule("chat", self.settings.rate_limit_chat_per_minute, 60)
        if method == "POST" and path == f"{prefix}/search":
            return RateLimitRule("search", self.settings.rate_limit_search_per_minute, 60)
        if method == "POST" and path.startswith(f"{prefix}/kb/") and path.endswith("/documents"):
            return RateLimitRule("upload", self.settings.rate_limit_upload_per_minute, 60)
        if method == "POST" and (
            path.endswith("/reindex")
            or path.endswith("/retry-indexing")
            or path.endswith("/retry-failed")
            or path.endswith("/cancel")
            or path.endswith("/pause")
            or path.endswith("/resume")
        ):
            return RateLimitRule("index_ops", self.settings.rate_limit_index_ops_per_10m, 600)
        return None

    def _identity(self, request: Request) -> tuple[str, bool]:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
            try:
                payload = jwt.decode(token, self.settings.secret_key, algorithms=[self.settings.algorithm])
                user_id = UUID(payload["sub"])
                return f"user:{user_id}", self._is_admin(user_id)
            except Exception:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
                return f"token:{digest}", False
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}", False

    @staticmethod
    def _is_admin(user_id: UUID) -> bool:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                return bool(user and user.role == UserRole.admin)
        except Exception:
            return False

    def _allow(self, rule: RateLimitRule, identity: str, limit: int) -> bool:
        try:
            redis = self._redis()
            bucket = int(time.time() // rule.window_seconds)
            key = f"rate_limit:{rule.name}:{identity}:{bucket}"
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, rule.window_seconds + 5)
            return int(count) <= limit
        except Exception:
            return True

    def _redis(self) -> Redis:
        if self.redis is None:
            self.redis = Redis.from_url(self.settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        return self.redis
