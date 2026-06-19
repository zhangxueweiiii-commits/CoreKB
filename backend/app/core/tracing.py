import uuid
from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings
from app.core.request_context import get_request_context, set_trace_id

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcOTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except Exception:  # pragma: no cover - optional dependency fallback
    trace = None
    GrpcOTLPSpanExporter = None
    OTLPSpanExporter = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None


_initialized = False


def setup_tracing() -> None:
    global _initialized
    settings = get_settings()
    if _initialized or not settings.otel_enabled or trace is None:
        return
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint and BatchSpanProcessor:
        exporter = _build_exporter(settings.otel_exporter_otlp_endpoint)
        if exporter:
            provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True


def _build_exporter(endpoint: str):
    if endpoint.endswith("/v1/traces") and OTLPSpanExporter:
        return OTLPSpanExporter(endpoint=endpoint)
    if ":4317" in endpoint and GrpcOTLPSpanExporter:
        return GrpcOTLPSpanExporter(endpoint=endpoint)
    if OTLPSpanExporter:
        http_endpoint = endpoint.rstrip("/")
        if not http_endpoint.endswith("/v1/traces"):
            http_endpoint = f"{http_endpoint}/v1/traces"
        return OTLPSpanExporter(endpoint=http_endpoint)
    if GrpcOTLPSpanExporter:
        return GrpcOTLPSpanExporter(endpoint=endpoint)
    return None


def current_trace_id() -> str | None:
    if trace is not None:
        span = trace.get_current_span()
        context = span.get_span_context()
        if context and context.is_valid:
            return f"{context.trace_id:032x}"
    return get_request_context().trace_id


def ensure_trace_id(existing: str | None = None) -> str:
    trace_id = existing or current_trace_id() or uuid.uuid4().hex
    set_trace_id(trace_id)
    return trace_id


@contextmanager
def start_span(name: str, **attributes: Any):
    setup_tracing()
    if trace is None or not get_settings().otel_enabled:
        ensure_trace_id()
        yield None
        return
    tracer = trace.get_tracer("corekb")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None and key.lower() not in {"api_key", "password", "document_text", "content"}:
                span.set_attribute(key, str(value)[:500])
        set_trace_id(current_trace_id())
        yield span
