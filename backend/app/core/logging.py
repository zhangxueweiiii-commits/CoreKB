import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.request_context import get_request_context
from app.core.tracing import current_trace_id


SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization", "file_content", "content"}
SENSITIVE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|password|secret|token|authorization)(\s*[=:]\s*)([^,\s]+)"
)


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_KEYS else sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]
    if isinstance(value, str):
        value = SENSITIVE_PATTERN.sub(r"\1\2[redacted]", value)
        if len(value) > 1000:
            return value[:1000]
        return value
    return value


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", None) or context.request_id,
            "trace_id": getattr(record, "trace_id", None) or current_trace_id(),
            "user_id": getattr(record, "user_id", None) or context.user_id,
            "module": record.name,
            "message": record.getMessage(),
        }
        error = getattr(record, "error", None)
        if error:
            payload["error"] = str(error)[:2000]
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)[:4000]
        for key in ["method", "path", "status_code", "duration_ms", "ip", "alert_type", "resource_id"]:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(sanitize_log_value(payload), ensure_ascii=False, default=str)


class SafeStreamHandler(logging.StreamHandler):
    def handleError(self, record: logging.LogRecord) -> None:
        exc = sys.exc_info()[1]
        if isinstance(exc, ValueError) and "closed file" in str(exc):
            return
        super().handleError(record)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = SafeStreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ["uvicorn.access"]:
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True
