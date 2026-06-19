from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.alert_event import AlertEvent, AlertEventStatus
from app.models.user import User
from app.schemas.alert import AlertEventRead

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertEventRead])
def list_alerts(
    status_filter: AlertEventStatus | None = Query(default=None, alias="status"),
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AlertEvent]:
    stmt = select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(AlertEvent.status == status_filter)
    if severity:
        stmt = stmt.where(AlertEvent.severity == severity)
    if alert_type:
        stmt = stmt.where(AlertEvent.alert_type == alert_type)
    return list(db.scalars(stmt).all())


def _update_status(alert_id: UUID, new_status: AlertEventStatus, db: Session) -> AlertEvent:
    alert = db.get(AlertEvent, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert event not found")
    alert.status = new_status
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertEventRead)
def resolve_alert(
    alert_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertEvent:
    return _update_status(alert_id, AlertEventStatus.resolved, db)


@router.patch("/{alert_id}/ignore", response_model=AlertEventRead)
def ignore_alert(
    alert_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertEvent:
    return _update_status(alert_id, AlertEventStatus.ignored, db)
