from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.maintenance import MaintenanceExperienceCandidateStatus
from app.models.user import User, UserRole
from app.schemas.maintenance import (
    MaintenanceCandidateAcceptResponse,
    MaintenanceCandidateReviewRequest,
    MaintenanceExperienceCandidateCreate,
    MaintenanceExperienceCandidateRead,
    MaintenanceKnowledgeEntryRead,
    MaintenanceRecordDraftCreate,
    MaintenanceRecordDraftRead,
)
from app.services.maintenance_curation_service import MaintenanceCurationService

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _require_reviewer(user: User) -> None:
    if user.role not in {UserRole.admin, UserRole.editor}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Maintenance reviewer role required")


@router.post("/record-drafts", response_model=MaintenanceRecordDraftRead, status_code=status.HTTP_201_CREATED)
def create_maintenance_record_draft(
    payload: MaintenanceRecordDraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return MaintenanceCurationService(db).create_record_draft(payload, current_user)


@router.post("/experience-candidates", response_model=MaintenanceExperienceCandidateRead, status_code=status.HTTP_201_CREATED)
def create_maintenance_experience_candidate(
    payload: MaintenanceExperienceCandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return MaintenanceCurationService(db).create_candidate(payload, current_user)


@router.get("/experience-candidates", response_model=list[MaintenanceExperienceCandidateRead])
def list_maintenance_experience_candidates(
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if status_filter:
        try:
            MaintenanceExperienceCandidateStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid candidate status") from exc
    return MaintenanceCurationService(db).list_candidates(status_filter)


@router.post("/experience-candidates/{candidate_id}/accept", response_model=MaintenanceCandidateAcceptResponse)
def accept_maintenance_experience_candidate(
    candidate_id: UUID,
    payload: MaintenanceCandidateReviewRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_reviewer(current_user)
    candidate, entry = MaintenanceCurationService(db).accept_candidate(
        candidate_id,
        current_user,
        payload.reviewer_note if payload else None,
    )
    return {"candidate": candidate, "knowledge_entry": entry}


@router.post("/experience-candidates/{candidate_id}/reject", response_model=MaintenanceExperienceCandidateRead)
def reject_maintenance_experience_candidate(
    candidate_id: UUID,
    payload: MaintenanceCandidateReviewRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_reviewer(current_user)
    return MaintenanceCurationService(db).reject_candidate(
        candidate_id,
        current_user,
        payload.reviewer_note if payload else None,
    )
