from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import assert_can_edit_kb, assert_can_view_kb, get_current_user, get_kb_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models.document import Document, DocumentMetadataSuggestion, DocumentMetadataSuggestionStatus, DocumentStatus
from app.models.user import User
from app.schemas.document import (
    DocumentMetadataSuggestionAcceptRequest,
    DocumentMetadataSuggestionListResponse,
    DocumentMetadataSuggestionRead,
    DocumentRead,
)
from app.schemas.index_job import IndexJobSummary
from app.schemas.validation_report import ValidationReportRead
from app.core.metrics import DOCUMENT_UPLOADS_TOTAL, INDEX_JOBS_TOTAL
from app.services.audit_service import AuditService
from app.services.document_metadata_completeness_service import DocumentMetadataCompletenessService
from app.services.document_metadata_suggester import DocumentMetadataSuggester, SUPPORTED_METADATA_FIELDS
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_parser import DocumentParser
from app.services.index_job_service import IndexJobService
from app.services.validation_report_service import (
    get_validation_report as get_validation_report_by_id,
    list_validation_reports_by_document,
)
from app.services.vector_store import VectorStore
from app.tasks.document_tasks import enqueue_reindex_job

router = APIRouter(tags=["documents"])


def _document_read(document: Document) -> dict:
    return {
        "id": document.id,
        "knowledge_base_id": document.knowledge_base_id,
        "filename": document.filename,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "status": document.status,
        "error_message": document.error_message,
        "chunk_count": document.chunk_count,
        "meta": document.meta or {},
        "metadata_completeness": DocumentMetadataCompletenessService().evaluate(document),
        "indexed_at": document.indexed_at,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _suggestion_read(suggestion: DocumentMetadataSuggestion, document: Document) -> dict:
    return {
        "id": suggestion.id,
        "document_id": suggestion.document_id,
        "field": suggestion.field,
        "raw_value": suggestion.raw_value,
        "normalized_value": suggestion.normalized_value,
        "normalization_source": suggestion.normalization_source,
        "dictionary_entry_id": suggestion.dictionary_entry_id,
        "custom_value": suggestion.custom_value,
        "suggested_value": suggestion.suggested_value,
        "confidence": suggestion.confidence.value,
        "source": suggestion.source.value,
        "evidence_excerpt": suggestion.evidence_excerpt,
        "rule_name": suggestion.rule_name,
        "status": suggestion.status.value,
        "reviewed_by": suggestion.reviewed_by,
        "reviewed_at": suggestion.reviewed_at,
        "created_at": suggestion.created_at,
        "current_value": (document.meta or {}).get(suggestion.field),
        "review_guardrails": _suggestion_review_guardrails(suggestion, document),
    }


def _suggestion_review_guardrails(suggestion: DocumentMetadataSuggestion, document: Document) -> dict:
    current_value = (document.meta or {}).get(suggestion.field)
    warnings: list[str] = []
    if current_value not in (None, ""):
        warnings.append("This field already has a formal metadata value. Review before replacing it.")
    if suggestion.confidence.value == "low":
        warnings.append("This suggestion has low confidence and needs careful review.")
    if suggestion.normalization_source == "fallback":
        warnings.append("This value was not matched by dictionary or rule normalization.")
    return {
        "requires_evidence_review": True,
        "requires_current_value_review": current_value not in (None, ""),
        "requires_custom_value_flag": suggestion.normalization_source == "fallback",
        "reindex_required_on_accept": True,
        "warnings": warnings,
        "checklist": [
            "Review the evidence excerpt.",
            "Compare the suggestion with the current formal metadata value.",
            "Confirm the normalization source.",
            "Use custom_value=true for non-standard values.",
            "Expect a single-document reindex after accept.",
        ],
    }


def _validation_report_read(report) -> dict:
    return {
        "id": report.id,
        "document_id": report.document_id,
        "report_type": report.report_type.value,
        "severity": report.severity.value,
        "issue_count": report.issue_count,
        "issues_json": report.issues_json,
        "summary": report.summary,
        "status": report.status.value,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def _get_document_or_404(db: Session, document_id: UUID) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _assert_can_edit_document(db: Session, user: User, document: Document) -> None:
    kb = get_kb_or_404(db, document.knowledge_base_id)
    assert_can_edit_kb(db, user, kb)


def _assert_can_view_document(db: Session, user: User, document: Document) -> None:
    kb = get_kb_or_404(db, document.knowledge_base_id)
    assert_can_view_kb(db, user, kb)


@router.post("/kb/{kb_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    kb = get_kb_or_404(db, kb_id)
    assert_can_edit_kb(db, current_user, kb)
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in DocumentParser.supported_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    content = await file.read()
    settings = get_settings()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    target_dir = settings.upload_dir / str(kb_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4()}{suffix}"
    target_path = target_dir / stored_name
    target_path.write_bytes(content)

    document = Document(
        knowledge_base_id=kb_id,
        filename=filename,
        file_path=str(target_path),
        file_type=suffix.lstrip("."),
        file_size=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    job = IndexJobService(db).create_document_job(document, current_user)
    enqueue_reindex_job(job.id)
    DOCUMENT_UPLOADS_TOTAL.inc()
    INDEX_JOBS_TOTAL.labels(job.job_type.value).inc()
    AuditService(db).record(
        actor=current_user,
        action="document.upload",
        resource_type="document",
        resource_id=document.id,
        knowledge_base_id=kb_id,
        document_id=document.id,
        status="success",
        metadata={"filename": filename, "file_type": document.file_type, "file_size": len(content)},
    )
    return document


@router.get("/kb/{kb_id}/documents", response_model=list[DocumentRead])
def list_documents(
    kb_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    kb = get_kb_or_404(db, kb_id)
    assert_can_view_kb(db, current_user, kb)
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.knowledge_base_id == kb_id)
            .order_by(Document.created_at.desc())
        ).all()
    )
    return [_document_read(document) for document in documents]


@router.get("/documents/metadata-suggestions", response_model=DocumentMetadataSuggestionListResponse)
def list_all_metadata_suggestions(
    status_filter: str | None = Query(default=None, alias="status"),
    field: str | None = None,
    confidence: str | None = None,
    document_id: UUID | None = None,
    knowledge_base_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(DocumentMetadataSuggestion, Document).join(Document, Document.id == DocumentMetadataSuggestion.document_id)
    if status_filter:
        stmt = stmt.where(DocumentMetadataSuggestion.status == DocumentMetadataSuggestionStatus(status_filter))
    if field:
        stmt = stmt.where(DocumentMetadataSuggestion.field == field)
    if confidence:
        stmt = stmt.where(DocumentMetadataSuggestion.confidence == confidence)
    if document_id:
        stmt = stmt.where(DocumentMetadataSuggestion.document_id == document_id)
    if knowledge_base_id:
        stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
    rows = db.execute(stmt.order_by(DocumentMetadataSuggestion.created_at.desc()).limit(200)).all()
    items: list[dict] = []
    for suggestion, document in rows:
        _assert_can_view_document(db, current_user, document)
        items.append(_suggestion_read(suggestion, document))
    return {"items": items, "total": len(items)}


@router.post(
    "/documents/{document_id}/metadata-suggestions/generate",
    response_model=DocumentMetadataSuggestionListResponse,
)
def generate_metadata_suggestions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_document_or_404(db, document_id)
    _assert_can_edit_document(db, current_user, document)
    try:
        suggestions = DocumentMetadataSuggester(db).generate_suggestions(document)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    AuditService(db).record(
        actor=current_user,
        action="document.metadata_suggestions.generate",
        resource_type="document",
        resource_id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        document_id=document.id,
        status="success",
        metadata={"suggestion_count": len(suggestions)},
    )
    return {"items": [_suggestion_read(suggestion, document) for suggestion in suggestions], "total": len(suggestions)}


@router.get("/validation-reports/{report_id}", response_model=ValidationReportRead)
def get_validation_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = get_validation_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation report not found")
    document = _get_document_or_404(db, report.document_id)
    _assert_can_view_document(db, current_user, document)
    return _validation_report_read(report)


@router.get("/documents/{document_id}/validation-reports", response_model=list[ValidationReportRead])
def list_document_validation_reports(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    document = _get_document_or_404(db, document_id)
    _assert_can_view_document(db, current_user, document)
    reports = list_validation_reports_by_document(db, document.id)
    return [_validation_report_read(report) for report in reports]


@router.get(
    "/documents/{document_id}/metadata-suggestions",
    response_model=DocumentMetadataSuggestionListResponse,
)
def list_document_metadata_suggestions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_document_or_404(db, document_id)
    _assert_can_view_document(db, current_user, document)
    suggestions = list(
        db.scalars(
            select(DocumentMetadataSuggestion)
            .where(DocumentMetadataSuggestion.document_id == document.id)
            .order_by(DocumentMetadataSuggestion.created_at.desc())
        ).all()
    )
    return {"items": [_suggestion_read(suggestion, document) for suggestion in suggestions], "total": len(suggestions)}


@router.post(
    "/documents/{document_id}/metadata-suggestions/{suggestion_id}/accept",
    response_model=DocumentMetadataSuggestionRead,
)
def accept_metadata_suggestion(
    document_id: UUID,
    suggestion_id: UUID,
    payload: DocumentMetadataSuggestionAcceptRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_document_or_404(db, document_id)
    _assert_can_edit_document(db, current_user, document)
    suggestion = db.get(DocumentMetadataSuggestion, suggestion_id)
    if not suggestion or suggestion.document_id != document.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata suggestion not found")
    if suggestion.field not in SUPPORTED_METADATA_FIELDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported metadata field")
    try:
        suggestion = DocumentMetadataSuggester(db).accept_suggestion(
            document,
            suggestion,
            current_user,
            payload.value if payload else None,
            payload.custom_value if payload else False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    document.status = DocumentStatus.uploaded
    document.error_message = None
    document.indexed_at = None
    db.commit()
    db.refresh(document)
    job = IndexJobService(db).create_document_job(document, current_user)
    enqueue_reindex_job(job.id)
    INDEX_JOBS_TOTAL.labels(job.job_type.value).inc()
    AuditService(db).record(
        actor=current_user,
        action="document.metadata_suggestion.accept",
        resource_type="document_metadata_suggestion",
        resource_id=suggestion.id,
        knowledge_base_id=document.knowledge_base_id,
        document_id=document.id,
        status="success",
        metadata={
            "field": suggestion.field,
            "value": suggestion.suggested_value,
            "suggestion_id": str(suggestion.id),
            "index_job_id": str(job.id),
            "reindex_triggered": True,
            "custom_value": suggestion.custom_value,
        },
    )
    return _suggestion_read(suggestion, document)


@router.post(
    "/documents/{document_id}/metadata-suggestions/{suggestion_id}/reject",
    response_model=DocumentMetadataSuggestionRead,
)
def reject_metadata_suggestion(
    document_id: UUID,
    suggestion_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_document_or_404(db, document_id)
    _assert_can_edit_document(db, current_user, document)
    suggestion = db.get(DocumentMetadataSuggestion, suggestion_id)
    if not suggestion or suggestion.document_id != document.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata suggestion not found")
    suggestion = DocumentMetadataSuggester(db).reject_suggestion(suggestion, current_user)
    AuditService(db).record(
        actor=current_user,
        action="document.metadata_suggestion.reject",
        resource_type="document_metadata_suggestion",
        resource_id=suggestion.id,
        knowledge_base_id=document.knowledge_base_id,
        document_id=document.id,
        status="success",
        metadata={
            "field": suggestion.field,
            "suggestion_id": str(suggestion.id),
            "rejected_status": suggestion.status.value,
        },
    )
    return _suggestion_read(suggestion, document)


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    document = _get_document_or_404(db, document_id)
    _assert_can_view_document(db, current_user, document)
    return _document_read(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    kb = get_kb_or_404(db, document.knowledge_base_id)
    assert_can_edit_kb(db, current_user, kb)
    try:
        await VectorStore().delete_document(str(document.id))
    except Exception:
        pass
    AuditService(db).record(
        actor=current_user,
        action="document.delete",
        resource_type="document",
        resource_id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        document_id=document.id,
        status="success",
        metadata={"filename": document.filename},
    )
    db.delete(document)
    db.commit()


@router.post("/documents/{document_id}/retry-indexing", response_model=IndexJobSummary)
async def retry_indexing(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndexJobSummary:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    kb = get_kb_or_404(db, document.knowledge_base_id)
    assert_can_edit_kb(db, current_user, kb)
    if document.status.value not in {"failed", "uploaded", "parsed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed, uploaded, or parsed documents can be retried",
        )
    document.status = DocumentStatus.uploaded
    document.error_message = None
    document.chunk_count = 0
    document.indexed_at = None
    db.commit()
    db.refresh(document)
    job = IndexJobService(db).create_document_job(document, current_user)
    enqueue_reindex_job(job.id)
    INDEX_JOBS_TOTAL.labels(job.job_type.value).inc()
    AuditService(db).record(
        actor=current_user,
        action="document.retry_indexing",
        resource_type="index_job",
        resource_id=job.id,
        knowledge_base_id=document.knowledge_base_id,
        document_id=document.id,
        status="success",
    )
    return job
