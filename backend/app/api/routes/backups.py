from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.backup_job import BackupJob, BackupJobStatus, BackupJobType
from app.models.user import User
from app.schemas.backup import BackupJobRead, BackupVerifyResponse
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("", response_model=list[BackupJobRead])
def list_backups(
    status_filter: BackupJobStatus | None = Query(default=None, alias="status"),
    job_type: BackupJobType | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[BackupJob]:
    stmt = select(BackupJob).order_by(BackupJob.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        stmt = stmt.where(BackupJob.status == status_filter)
    if job_type:
        stmt = stmt.where(BackupJob.job_type == job_type)
    return list(db.scalars(stmt).all())


@router.post("/{backup_id}/verify", response_model=BackupVerifyResponse)
def verify_backup(
    backup_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupVerifyResponse:
    backup = db.get(BackupJob, backup_id)
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup job not found")
    verified, actual = BackupService(db).verify(backup)
    return BackupVerifyResponse(
        backup_id=backup.id,
        verified=verified,
        expected_checksum=backup.checksum,
        actual_checksum=actual,
    )
