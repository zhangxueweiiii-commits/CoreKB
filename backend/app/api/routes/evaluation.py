from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User
from app.schemas.evaluation import (
    AssistantEvaluationCompareResponse,
    AssistantEvaluationRunRequest,
    AssistantEvaluationResponse,
    AnnotationSummaryResponse,
    EvaluationCaseCompareResponse,
    EvaluationCaseAnnotationCreate,
    EvaluationCaseAnnotationListResponse,
    EvaluationCaseAnnotationRead,
    EvaluationCaseAnnotationUpdate,
    EvaluationCaseResultRead,
    EvaluationFailureTriageNoteListItem,
    EvaluationFailureTriageNotePayload,
    EvaluationFailureTriageNoteRead,
    EvaluationRunCompareResponse,
    EvaluationRunListItem,
    EvaluationRunMetadataUpdateRequest,
    AssistantTrendResponse,
    EvaluationRunRead,
    ImprovementGenerateRequest,
    ImprovementAnnotationListResponse,
    ImprovementItemDetailRead,
    ImprovementItemRead,
    ImprovementSummary,
    ImprovementUpdateRequest,
    OverallTrendResponse,
    RegressionCreateRequest,
    RegressionRead,
    RegressionSummary,
    RegressionTrendResponse,
    RetrievalEvaluationCompareResponse,
    RetrievalEvaluationResponse,
    RetrievalEvaluationRunRequest,
)
from app.services.evaluation_annotation_stats_service import EvaluationAnnotationStatsService
from app.services.evaluation_case_annotation_service import EvaluationCaseAnnotationService
from app.services.evaluation_improvement_service import EvaluationImprovementService
from app.services.evaluation_case_drilldown_service import EvaluationCaseDrilldownService
from app.services.evaluation_failure_triage_note_service import EvaluationFailureTriageNoteService
from app.services.evaluation_regression_service import EvaluationRegressionService
from app.services.evaluation_run_compare_service import EvaluationRunCompareService
from app.services.evaluation_run_metadata_service import EvaluationRunMetadataService
from app.services.evaluation_service import EvaluationService
from app.services.evaluation_trend_service import EvaluationTrendService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/retrieval/run", response_model=RetrievalEvaluationResponse)
async def run_retrieval_evaluation(
    payload: RetrievalEvaluationRunRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RetrievalEvaluationResponse:
    service = EvaluationService()
    readiness = service.ensure_evaluation_kb_ready(db)
    if not readiness.evaluation_kb_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first.",
                "evaluation_kb_id": str(readiness.evaluation_kb_id) if readiness.evaluation_kb_id else None,
                "evaluation_kb_ready": readiness.evaluation_kb_ready,
                "missing_documents": readiness.missing_documents,
                "unindexed_documents": readiness.unindexed_documents,
            },
        )
    return await service.run_retrieval_eval(
        db=db,
        user=current_user,
        use_metadata_filter=payload.use_metadata_filter if payload else False,
        use_rerank=payload.use_rerank if payload else False,
        rerank_top_n=payload.rerank_top_n if payload else None,
    )


@router.post("/retrieval/compare", response_model=RetrievalEvaluationCompareResponse)
async def compare_retrieval_evaluation(
    payload: RetrievalEvaluationRunRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RetrievalEvaluationCompareResponse:
    service = EvaluationService()
    readiness = service.ensure_evaluation_kb_ready(db)
    if not readiness.evaluation_kb_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first.",
                "evaluation_kb_id": str(readiness.evaluation_kb_id) if readiness.evaluation_kb_id else None,
                "evaluation_kb_ready": readiness.evaluation_kb_ready,
                "missing_documents": readiness.missing_documents,
                "unindexed_documents": readiness.unindexed_documents,
            },
        )
    return await service.compare_retrieval_eval(
        db=db,
        user=current_user,
        rerank_top_n=payload.rerank_top_n if payload else None,
    )


@router.get("/retrieval/latest", response_model=EvaluationRunRead | None)
def latest_retrieval_evaluation(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EvaluationRun | None:
    return db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.eval_type == EvaluationType.retrieval)
        .order_by(EvaluationRun.created_at.desc())
    )


@router.post("/assistants/run", response_model=AssistantEvaluationResponse)
async def run_assistant_evaluation(
    payload: AssistantEvaluationRunRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AssistantEvaluationResponse:
    service = EvaluationService()
    readiness = service.ensure_evaluation_kb_ready(db)
    if not readiness.evaluation_kb_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first.",
                "evaluation_kb_id": str(readiness.evaluation_kb_id) if readiness.evaluation_kb_id else None,
                "evaluation_kb_ready": readiness.evaluation_kb_ready,
                "missing_documents": readiness.missing_documents,
                "unindexed_documents": readiness.unindexed_documents,
            },
        )
    try:
        return await service.run_assistant_eval(
            db=db,
            user=current_user,
            use_metadata_filter=payload.use_metadata_filter if payload else True,
            use_rerank=payload.use_rerank if payload else True,
            rerank_top_n=payload.rerank_top_n if payload else None,
            run_label=payload.run_label if payload else None,
            change_type=payload.change_type if payload else "unknown",
            change_summary=payload.change_summary if payload else None,
            operator_notes=payload.operator_notes if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/assistants/compare", response_model=AssistantEvaluationCompareResponse)
async def compare_assistant_evaluation(
    payload: AssistantEvaluationRunRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AssistantEvaluationCompareResponse:
    service = EvaluationService()
    readiness = service.ensure_evaluation_kb_ready(db)
    if not readiness.evaluation_kb_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first.",
                "evaluation_kb_id": str(readiness.evaluation_kb_id) if readiness.evaluation_kb_id else None,
                "evaluation_kb_ready": readiness.evaluation_kb_ready,
                "missing_documents": readiness.missing_documents,
                "unindexed_documents": readiness.unindexed_documents,
            },
        )
    return await service.compare_assistant_eval(
        db=db,
        user=current_user,
        rerank_top_n=payload.rerank_top_n if payload else None,
    )


@router.get("/assistants/latest", response_model=AssistantEvaluationResponse | None)
def latest_assistant_evaluation(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AssistantEvaluationResponse | None:
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.eval_type == EvaluationType.assistant)
        .order_by(EvaluationRun.created_at.desc())
    )
    return EvaluationService.assistant_response_from_run(run) if run else None


@router.get("/runs", response_model=list[EvaluationRunListItem])
def list_evaluation_runs(
    eval_type: str | None = None,
    change_type: str | None = None,
    assistant_type: str | None = None,
    limit: int = 50,
    order_by: str = "created_at",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    try:
        return EvaluationRunMetadataService(db).list_runs(
            eval_type=eval_type,
            change_type=change_type,
            assistant_type=assistant_type,
            limit=limit,
            order_by=order_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/runs/{run_id}/metadata", response_model=EvaluationRunRead)
def update_evaluation_run_metadata(
    run_id: UUID,
    payload: EvaluationRunMetadataUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationRunMetadataService(db).update_metadata(
            run_id=run_id,
            user=current_user,
            run_label=payload.run_label,
            change_type=payload.change_type,
            change_summary=payload.change_summary,
            operator_notes=payload.operator_notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs/compare", response_model=EvaluationRunCompareResponse)
def compare_evaluation_runs(
    before_run_id: UUID,
    after_run_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationRunCompareService(db).compare_evaluation_runs(before_run_id, after_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/case-annotations", response_model=EvaluationCaseAnnotationListResponse)
def list_case_annotations(
    assistant_type: str | None = None,
    human_root_cause: str | None = None,
    human_fix_type: str | None = None,
    handling_status: str | None = None,
    evaluation_run_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    keyword: str | None = None,
    improvement_item_id: UUID | None = None,
    improvement_status: str | None = None,
    regression_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    order_by: str = "annotated_at",
    order_direction: str = "desc",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationCaseAnnotationService(db).list_annotations(
            assistant_type=assistant_type,
            human_root_cause=human_root_cause,
            human_fix_type=human_fix_type,
            handling_status=handling_status,
            evaluation_run_id=evaluation_run_id,
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            improvement_item_id=improvement_item_id,
            improvement_status=improvement_status,
            regression_status=regression_status,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/triage-notes", response_model=list[EvaluationFailureTriageNoteListItem])
def list_failure_triage_notes(
    evaluation_run_id: UUID | None = None,
    triage_status: str | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    try:
        return EvaluationFailureTriageNoteService(db).list_notes(
            evaluation_run_id=evaluation_run_id,
            triage_status=triage_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cases/{case_result_id}/triage-note", response_model=EvaluationFailureTriageNoteRead | None)
def get_failure_triage_note(
    case_result_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object | None:
    try:
        return EvaluationFailureTriageNoteService(db).get_note(case_result_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{case_result_id}/triage-note", response_model=EvaluationFailureTriageNoteRead)
def upsert_failure_triage_note(
    case_result_id: UUID,
    payload: EvaluationFailureTriageNotePayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationFailureTriageNoteService(db).upsert_note(
            case_result_id=case_result_id,
            user=current_user,
            triage_status=payload.triage_status,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/cases/{case_result_id}/triage-note", response_model=EvaluationFailureTriageNoteRead)
def update_failure_triage_note(
    case_result_id: UUID,
    payload: EvaluationFailureTriageNotePayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationFailureTriageNoteService(db).upsert_note(
            case_result_id=case_result_id,
            user=current_user,
            triage_status=payload.triage_status,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

@router.get("/annotations/summary", response_model=AnnotationSummaryResponse)
def annotation_summary(
    evaluation_run_id: UUID | None = None,
    assistant_type: str | None = None,
    handling_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationAnnotationStatsService(db).get_annotation_summary(
            evaluation_run_id=evaluation_run_id,
            assistant_type=assistant_type,
            handling_status=handling_status,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cases/{case_result_id}", response_model=EvaluationCaseResultRead)
def get_evaluation_case_result(
    case_result_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationCaseDrilldownService(db).get_case_result(case_result_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/cases/{case_result_id}/annotation", response_model=EvaluationCaseAnnotationRead | None)
def get_case_annotation(
    case_result_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object | None:
    try:
        return EvaluationCaseAnnotationService(db).get_annotation(case_result_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{case_result_id}/annotation", response_model=EvaluationCaseAnnotationRead)
def upsert_case_annotation(
    case_result_id: UUID,
    payload: EvaluationCaseAnnotationCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationCaseAnnotationService(db).upsert_annotation(
            case_result_id=case_result_id,
            user=current_user,
            human_judgement=payload.human_judgement,
            human_root_cause=payload.human_root_cause,
            human_fix_type=payload.human_fix_type,
            handling_status=payload.handling_status,
            handling_notes=payload.handling_notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/cases/{case_result_id}/annotation", response_model=EvaluationCaseAnnotationRead)
def update_case_annotation(
    case_result_id: UUID,
    payload: EvaluationCaseAnnotationUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationCaseAnnotationService(db).update_annotation(
            case_result_id=case_result_id,
            user=current_user,
            human_judgement=payload.human_judgement,
            human_root_cause=payload.human_root_cause,
            human_fix_type=payload.human_fix_type,
            handling_status=payload.handling_status,
            handling_notes=payload.handling_notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/runs/compare/cases/{case_id}", response_model=EvaluationCaseCompareResponse)
def compare_evaluation_case(
    case_id: str,
    before_run_id: UUID,
    after_run_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationCaseDrilldownService(db).compare_case(before_run_id, after_run_id, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/trends/assistants", response_model=AssistantTrendResponse)
def assistant_metric_trends(
    assistant_type: str | None = None,
    metric: str | None = None,
    limit: int = 20,
    use_metadata_filter: bool | None = None,
    use_rerank: bool | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return EvaluationTrendService(db).get_assistant_metric_trends(
        assistant_type=assistant_type,
        metric=metric,
        limit=limit,
        use_metadata_filter=use_metadata_filter,
        use_rerank=use_rerank,
    )


@router.get("/trends/overall", response_model=OverallTrendResponse)
def overall_metric_trends(
    metric: str | None = None,
    limit: int = 20,
    use_metadata_filter: bool | None = None,
    use_rerank: bool | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return EvaluationTrendService(db).get_overall_metric_trends(
        limit=limit,
        metric=metric,
        use_metadata_filter=use_metadata_filter,
        use_rerank=use_rerank,
    )


@router.get("/trends/regressions", response_model=RegressionTrendResponse)
def regression_trends(
    limit: int = 20,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return EvaluationTrendService(db).get_regression_trends(limit=limit)


@router.post("/improvements/generate", response_model=list[ImprovementItemRead])
def generate_improvements(
    payload: ImprovementGenerateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    try:
        return EvaluationImprovementService(db).generate_improvement_items(
            evaluation_run_id=payload.evaluation_run_id,
            user=current_user,
            force=payload.force,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/improvements", response_model=list[ImprovementItemRead])
def list_improvements(
    assistant_type: str | None = None,
    fix_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    try:
        return EvaluationImprovementService(db).list_items(
            assistant_type=assistant_type,
            fix_type=fix_type,
            status=status,
            priority=priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/improvements/summary", response_model=ImprovementSummary)
def improvements_summary(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return EvaluationImprovementService(db).summary()


@router.get("/improvements/{item_id}/annotations", response_model=ImprovementAnnotationListResponse)
def improvement_annotations(
    item_id: UUID,
    page: int = 1,
    page_size: int = 20,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationImprovementService(db).annotations_for_item(item_id, page=page, page_size=page_size)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/improvements/{item_id}", response_model=ImprovementItemDetailRead)
def get_improvement(
    item_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return EvaluationImprovementService(db).get_item_detail(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/improvements/{item_id}", response_model=ImprovementItemRead)
def update_improvement(
    item_id: UUID,
    payload: ImprovementUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationImprovementService(db).update_item(
            item_id=item_id,
            user=current_user,
            status=payload.status,
            suggested_action=payload.suggested_action,
            resolved_evaluation_run_id=payload.resolved_evaluation_run_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/regressions/create", response_model=RegressionRead)
def create_regression(
    payload: RegressionCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    try:
        return EvaluationRegressionService(db).create_regression(
            before_run_id=payload.before_evaluation_run_id,
            after_run_id=payload.after_evaluation_run_id,
            improvement_item_ids=payload.improvement_item_ids,
            user=current_user,
            notes=payload.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/regressions", response_model=list[RegressionRead])
def list_regressions(
    assistant_type: str | None = None,
    fix_type: str | None = None,
    regression_passed: bool | None = None,
    before_evaluation_run_id: UUID | None = None,
    after_evaluation_run_id: UUID | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    return EvaluationRegressionService(db).list_regressions(
        assistant_type=assistant_type,
        fix_type=fix_type,
        regression_passed=regression_passed,
        before_evaluation_run_id=before_evaluation_run_id,
        after_evaluation_run_id=after_evaluation_run_id,
    )


@router.get("/regressions/summary", response_model=RegressionSummary)
def regressions_summary(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return EvaluationRegressionService(db).get_regression_summary()


@router.get("/regressions/{regression_id}", response_model=RegressionRead)
def get_regression(
    regression_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    regression = EvaluationRegressionService(db).get_regression(regression_id)
    if not regression:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regression not found")
    return regression
