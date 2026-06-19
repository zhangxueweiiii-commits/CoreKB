import json
import logging
from pathlib import Path
from types import SimpleNamespace

from app.core import tracing
from app.core.logging import JsonLogFormatter


def formatted_message(logger_name: str, message: str) -> dict:
    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    return json.loads(JsonLogFormatter().format(record))


def test_tracing_disabled_still_runs(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "get_settings", lambda: SimpleNamespace(otel_enabled=False))

    with tracing.start_span("test.disabled"):
        trace_id = tracing.ensure_trace_id()

    assert trace_id


def test_tracing_enabled_logs_trace_id(monkeypatch) -> None:
    monkeypatch.setattr(
        tracing,
        "get_settings",
        lambda: SimpleNamespace(
            otel_enabled=True,
            otel_exporter_otlp_endpoint=None,
            otel_service_name="corekb-test",
        ),
    )

    with tracing.start_span("test.enabled"):
        tracing.ensure_trace_id("trace-test-123")
        payload = formatted_message("corekb.test", "hello")

    assert payload["trace_id"] == "trace-test-123"


def test_tracing_enabled_with_endpoint_initializes(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_initialized", False)
    monkeypatch.setattr(
        tracing,
        "get_settings",
        lambda: SimpleNamespace(
            otel_enabled=True,
            otel_exporter_otlp_endpoint="http://otel-collector:4317",
            otel_service_name="corekb-test",
        ),
    )

    tracing.setup_tracing()

    assert tracing.ensure_trace_id()


def test_celery_task_log_contains_trace_id() -> None:
    tracing.ensure_trace_id("celery-trace-123")

    payload = formatted_message("app.tasks.document_tasks", "task started")

    assert payload["module"] == "app.tasks.document_tasks"
    assert payload["trace_id"] == "celery-trace-123"


def test_tracing_logs_do_not_emit_secrets() -> None:
    tracing.ensure_trace_id("redaction-trace-123")

    payload = formatted_message("corekb.test", "api_key=sk-test password=secret token=abc")

    assert "sk-test" not in payload["message"]
    assert "secret" not in payload["message"]
    assert "abc" not in payload["message"]
    assert "[redacted]" in payload["message"]


def test_loki_profile_files_and_readme_exist() -> None:
    root = Path(__file__).resolve().parents[3]
    compose = root / "docker-compose.observability.yml"
    loki_config = root / "deploy" / "logging" / "loki" / "loki-config.yml"
    promtail_config = root / "deploy" / "logging" / "loki" / "promtail-config.yml"
    readme = root / "deploy" / "logging" / "loki" / "README.md"

    assert compose.exists()
    assert loki_config.exists()
    assert promtail_config.exists()
    assert readme.exists()
    assert "--profile observability" in readme.read_text(encoding="utf-8")


def test_otel_collector_example_files_and_readme_exist() -> None:
    root = Path(__file__).resolve().parents[3]
    config = root / "deploy" / "otel" / "otel-collector-config.yml"
    compose = root / "deploy" / "otel" / "docker-compose.otel.example.yml"
    readme = root / "deploy" / "otel" / "README.md"

    assert config.exists()
    assert compose.exists()
    assert readme.exists()
    assert "docker compose -f docker-compose.otel.example.yml up -d" in readme.read_text(encoding="utf-8")


def test_jaeger_apm_example_files_and_readme_exist() -> None:
    root = Path(__file__).resolve().parents[3]
    compose = root / "deploy" / "apm" / "jaeger" / "docker-compose.jaeger.example.yml"
    readme = root / "deploy" / "apm" / "jaeger" / "README.md"

    assert compose.exists()
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "docker compose -f docker-compose.jaeger.example.yml up -d" in text
    assert "trace_id" in text
