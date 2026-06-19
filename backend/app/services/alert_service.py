import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.alert_event import AlertEvent


logger = logging.getLogger("corekb.alerts")


class AlertService:
    def __init__(self, db: Session | None = None) -> None:
        self.settings = get_settings()
        self.db = db

    @contextmanager
    def _session(self):
        if self.db is not None:
            yield self.db
            return
        with SessionLocal() as db:
            yield db

    def send(
        self,
        *,
        alert_type: str,
        severity: str,
        message: str,
        resource_id: UUID | str | None = None,
        title: str | None = None,
        resource_type: str | None = None,
        metadata: dict | None = None,
    ) -> AlertEvent:
        with self._session() as db:
            event = AlertEvent(
                alert_type=alert_type,
                severity=severity,
                title=title or alert_type.replace("_", " ").title(),
                message=message[:2000],
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                webhook_sent=False,
                webhook_error=None,
                meta=metadata or {},
            )
            db.add(event)
            db.commit()
            db.refresh(event)

            if not self.settings.alert_enabled or not self.settings.alert_webhook_url:
                return event

            payload = {
                "alert_type": event.alert_type,
                "severity": event.severity,
                "title": event.title,
                "message": event.message,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                response = httpx.post(self.settings.alert_webhook_url, json=payload, timeout=5)
                response.raise_for_status()
                event.webhook_sent = True
                event.webhook_error = None
                logger.info("Alert sent", extra={"alert_type": alert_type, "resource_id": event.resource_id})
            except Exception as exc:
                event.webhook_sent = False
                event.webhook_error = str(exc)[:2000]
                logger.warning(
                    "Alert delivery failed",
                    extra={"alert_type": alert_type, "resource_id": event.resource_id, "error": str(exc)},
                )
            finally:
                db.commit()
                db.refresh(event)
            return event

    def index_job_failed(self, job_id: UUID, message: str) -> None:
        self.send(
            alert_type="index_job_failed",
            severity="warning",
            title="Index job failed",
            message=message,
            resource_type="index_job",
            resource_id=job_id,
        )

    def failed_job_threshold_exceeded(self, count: int) -> None:
        self.send(
            alert_type="failed_job_threshold_exceeded",
            severity="warning",
            title="Failed index job threshold exceeded",
            message=f"Recent failed index jobs reached {count}",
            resource_type="index_job",
            metadata={"failed_count": count},
        )

    def backup_failed(self, backup_id: UUID | None, message: str) -> None:
        if not self.settings.alert_backup_failed_enabled:
            return
        self.send(
            alert_type="backup_failed",
            severity="critical",
            title="Backup failed",
            message=message,
            resource_type="backup_job",
            resource_id=backup_id,
        )

    def health_unavailable(self, service_name: str) -> None:
        self.send(
            alert_type="health_unavailable",
            severity="critical",
            title=f"{service_name} unavailable",
            message=f"{service_name} health check failed",
            resource_type="health_check",
            resource_id=service_name,
        )
