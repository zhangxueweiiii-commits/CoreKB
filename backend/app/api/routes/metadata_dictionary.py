from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.metadata_dictionary import (
    MetadataDictionaryAliasRequest,
    MetadataDictionaryEntryCreate,
    MetadataDictionaryEntryRead,
    MetadataDictionaryEntryUpdate,
)
from app.services.metadata_dictionary_service import MetadataDictionaryService


router = APIRouter(prefix="/metadata-dictionary", tags=["metadata-dictionary"])


@router.get("", response_model=list[MetadataDictionaryEntryRead])
def list_metadata_dictionary(
    field_name: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    try:
        return MetadataDictionaryService(db).list_entries(
            field_name=field_name,
            status=status,
            keyword=keyword,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=MetadataDictionaryEntryRead, status_code=status.HTTP_201_CREATED)
def create_metadata_dictionary_entry(
    payload: MetadataDictionaryEntryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return MetadataDictionaryService(db).create_dictionary_entry(
            field_name=payload.field_name,
            canonical_value=payload.canonical_value,
            aliases=payload.aliases,
            user=current_user,
            description=payload.description,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{entry_id}", response_model=MetadataDictionaryEntryRead)
def update_metadata_dictionary_entry(
    entry_id: UUID,
    payload: MetadataDictionaryEntryUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return MetadataDictionaryService(db).update_dictionary_entry(
            entry_id=entry_id,
            canonical_value=payload.canonical_value,
            aliases=payload.aliases,
            status=payload.status,
            description=payload.description,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{entry_id}/aliases", response_model=MetadataDictionaryEntryRead)
def add_metadata_dictionary_alias(
    entry_id: UUID,
    payload: MetadataDictionaryAliasRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return MetadataDictionaryService(db).add_alias(entry_id, payload.alias)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{entry_id}/aliases/{alias}", response_model=MetadataDictionaryEntryRead)
def delete_metadata_dictionary_alias(
    entry_id: UUID,
    alias: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return MetadataDictionaryService(db).remove_alias(entry_id, alias)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
