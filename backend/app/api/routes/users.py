from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User
from app.models.user import UserRole
from app.schemas.user import UserCreate, UserRead, UserSearchResult, UserUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.get("/search", response_model=list[UserSearchResult])
def search_users(
    q: str = Query(default="", max_length=128),
    limit: int = Query(default=20, ge=1, le=50),
    kb_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserSearchResult]:
    if current_user.role != UserRole.admin:
        if kb_id is None or not PermissionService(db).can_manage_kb(current_user, kb_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User search not allowed")

    term = f"%{q.strip()}%"
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.username.asc()).limit(limit)
    if q.strip():
        stmt = stmt.where(
            or_(
                User.username.ilike(term),
                User.full_name.ilike(term),
                User.email.ilike(term),
            )
        )
    users = db.scalars(stmt).all()
    return [
        UserSearchResult(
            id=user.id,
            name=user.full_name or user.username,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    AuditService(db).record(
        actor=current_user,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        status="success",
        metadata={"username": user.username, "role": user.role.value},
    )
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updates = payload.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    for key, value in updates.items():
        setattr(user, key, value)
    if password:
        user.password_hash = get_password_hash(password)
    db.commit()
    db.refresh(user)
    AuditService(db).record(
        actor=current_user,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        status="success",
        metadata={"fields": [key for key in payload.model_dump(exclude_unset=True).keys() if key != "password"]},
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    AuditService(db).record(
        actor=current_user,
        action="user.delete",
        resource_type="user",
        resource_id=user.id,
        status="success",
        metadata={"username": user.username},
    )
    db.delete(user)
    db.commit()
