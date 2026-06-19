import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from app.core.request_context import RequestContext, get_request_context, set_request_context
from app.core.tracing import current_trace_id, ensure_trace_id, start_span


logger = logging.getLogger("corekb.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        incoming_trace_id = request.headers.get("X-Trace-ID")
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        set_request_context(
            RequestContext(
                request_id=request_id,
                trace_id=incoming_trace_id or uuid4().hex,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        ensure_trace_id(incoming_trace_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        error: str | None = None
        response: Response | None = None
        try:
            with start_span("http.request", method=request.method, path=request.url.path):
                response = await call_next(request)
                status_code = response.status_code
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Trace-ID"] = current_trace_id() or ""
                return response
        except Exception as exc:
            error = str(exc)
            logger.exception(
                "Unhandled request error",
                extra={"request_id": request_id, "error": error, "path": request.url.path},
            )
            raise
        finally:
            duration = time.perf_counter() - started
            path = request.url.path
            HTTP_REQUESTS_TOTAL.labels(request.method, path, str(status_code)).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(request.method, path).observe(duration)
            user_id = get_request_context().user_id
            logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "trace_id": current_trace_id(),
                    "user_id": user_id,
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "ip": ip_address,
                    "error": error,
                },
            )
