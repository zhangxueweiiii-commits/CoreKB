from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class RequestContext:
    request_id: str | None = None
    trace_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    user_id: str | None = None


_request_context: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())


def get_request_context() -> RequestContext:
    return _request_context.get()


def set_request_context(context: RequestContext) -> None:
    _request_context.set(context)


def set_request_user_id(user_id: str) -> None:
    context = _request_context.get()
    context.user_id = user_id
    _request_context.set(context)


def set_trace_id(trace_id: str | None) -> None:
    context = _request_context.get()
    context.trace_id = trace_id
    _request_context.set(context)
