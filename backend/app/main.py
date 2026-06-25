from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, assistants, audit_logs, auth, backups, chat, documents, evaluation, health, index_jobs, kb, maintenance, metadata, metadata_dictionary, metrics, search, system, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import setup_tracing
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware


configure_logging()
setup_tracing()
settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(kb.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(metadata_dictionary.router, prefix=settings.api_prefix)
app.include_router(metadata.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(assistants.router, prefix=settings.api_prefix)
app.include_router(maintenance.router, prefix=settings.api_prefix)
app.include_router(evaluation.router, prefix=settings.api_prefix)
app.include_router(system.router, prefix=settings.api_prefix)
app.include_router(index_jobs.router, prefix=settings.api_prefix)
app.include_router(audit_logs.router, prefix=settings.api_prefix)
app.include_router(backups.router, prefix=settings.api_prefix)
app.include_router(alerts.router, prefix=settings.api_prefix)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(metrics.router)
