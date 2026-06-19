from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.evaluation_annotation import (
    EvaluationCaseAnnotation,
    HandlingStatus,
    HumanFixType,
    HumanJudgement,
    HumanRootCause,
)
from app.models.evaluation_improvement import (
    EvaluationImprovementItem,
    EvaluationImprovementItemCaseResult,
    EvaluationImprovementRegressionStatus,
    EvaluationImprovementStatus,
)
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun
from app.models.user import User
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


ANNOTATION_LIST_ORDER_COLUMNS = {
    "annotated_at": EvaluationCaseAnnotation.annotated_at,
    "updated_at": EvaluationCaseAnnotation.updated_at,
    "case_id": EvaluationCaseResult.case_id,
    "assistant_type": EvaluationCaseResult.assistant_type,
}


class EvaluationCaseAnnotationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_annotation(self, case_result_id: UUID) -> EvaluationCaseAnnotation | None:
        self._require_case_result(case_result_id)
        return self._annotation_for_case(case_result_id)

    def upsert_annotation(
        self,
        case_result_id: UUID,
        user: User,
        human_judgement: str,
        human_root_cause: str,
        human_fix_type: str,
        handling_status: str,
        handling_notes: str | None = None,
    ) -> EvaluationCaseAnnotation:
        self._require_case_result(case_result_id)
        annotation = self._annotation_for_case(case_result_id)
        if annotation is None:
            annotation = EvaluationCaseAnnotation(evaluation_case_result_id=case_result_id)
            self.db.add(annotation)
        self._apply_values(
            annotation,
            user=user,
            human_judgement=human_judgement,
            human_root_cause=human_root_cause,
            human_fix_type=human_fix_type,
            handling_status=handling_status,
            handling_notes=handling_notes,
            update_notes=True,
        )
        self.db.commit()
        self.db.refresh(annotation)
        return annotation

    def update_annotation(
        self,
        case_result_id: UUID,
        user: User,
        human_judgement: str | None = None,
        human_root_cause: str | None = None,
        human_fix_type: str | None = None,
        handling_status: str | None = None,
        handling_notes: str | None = None,
    ) -> EvaluationCaseAnnotation:
        self._require_case_result(case_result_id)
        annotation = self._annotation_for_case(case_result_id)
        if annotation is None:
            raise KeyError("Evaluation case annotation not found")
        self._apply_values(
            annotation,
            user=user,
            human_judgement=human_judgement,
            human_root_cause=human_root_cause,
            human_fix_type=human_fix_type,
            handling_status=handling_status,
            handling_notes=handling_notes,
            update_notes=handling_notes is not None,
        )
        self.db.commit()
        self.db.refresh(annotation)
        return annotation

    def list_annotations(
        self,
        assistant_type: str | None = None,
        human_root_cause: str | None = None,
        human_fix_type: str | None = None,
        handling_status: str | None = None,
        evaluation_run_id: UUID | None = None,
        date_from=None,
        date_to=None,
        keyword: str | None = None,
        improvement_item_id: UUID | None = None,
        improvement_status: str | None = None,
        regression_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "annotated_at",
        order_direction: str = "desc",
    ) -> dict:
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        stmt = self._annotation_list_stmt(
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
        )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order_column = ANNOTATION_LIST_ORDER_COLUMNS.get(order_by)
        if order_column is None:
            raise ValueError(f"Invalid order_by: {order_by}")
        if order_direction not in {"asc", "desc"}:
            raise ValueError(f"Invalid order_direction: {order_direction}")
        order_expression = asc(order_column) if order_direction == "asc" else desc(order_column)
        rows = self.db.execute(
            stmt.order_by(order_expression).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return {
            "items": [self._annotation_list_item(annotation, case_result, run) for annotation, case_result, run in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    def list_annotation_models(
        self,
        assistant_type: str | None = None,
        human_root_cause: str | None = None,
        human_fix_type: str | None = None,
        handling_status: str | None = None,
        evaluation_run_id: UUID | None = None,
    ) -> list[EvaluationCaseAnnotation]:
        stmt = (
            select(EvaluationCaseAnnotation)
            .join(EvaluationCaseResult, EvaluationCaseResult.id == EvaluationCaseAnnotation.evaluation_case_result_id)
            .order_by(EvaluationCaseAnnotation.updated_at.desc())
        )
        if assistant_type:
            stmt = stmt.where(EvaluationCaseResult.assistant_type == assistant_type)
        if evaluation_run_id:
            stmt = stmt.where(EvaluationCaseResult.evaluation_run_id == evaluation_run_id)
        if human_root_cause:
            stmt = stmt.where(EvaluationCaseAnnotation.human_root_cause == HumanRootCause(human_root_cause))
        if human_fix_type:
            stmt = stmt.where(EvaluationCaseAnnotation.human_fix_type == HumanFixType(human_fix_type))
        if handling_status:
            stmt = stmt.where(EvaluationCaseAnnotation.handling_status == HandlingStatus(handling_status))
        return list(self.db.scalars(stmt).all())

    def _annotation_list_stmt(
        self,
        assistant_type: str | None = None,
        human_root_cause: str | None = None,
        human_fix_type: str | None = None,
        handling_status: str | None = None,
        evaluation_run_id: UUID | None = None,
        date_from=None,
        date_to=None,
        keyword: str | None = None,
        improvement_item_id: UUID | None = None,
        improvement_status: str | None = None,
        regression_status: str | None = None,
    ):
        stmt = (
            select(EvaluationCaseAnnotation, EvaluationCaseResult, EvaluationRun)
            .join(EvaluationCaseResult, EvaluationCaseResult.id == EvaluationCaseAnnotation.evaluation_case_result_id)
            .join(EvaluationRun, EvaluationRun.id == EvaluationCaseResult.evaluation_run_id)
        )
        if improvement_item_id or improvement_status or regression_status:
            stmt = (
                stmt.join(
                    EvaluationImprovementItemCaseResult,
                    EvaluationImprovementItemCaseResult.evaluation_case_result_id
                    == EvaluationCaseAnnotation.evaluation_case_result_id,
                )
                .join(
                    EvaluationImprovementItem,
                    EvaluationImprovementItem.id == EvaluationImprovementItemCaseResult.improvement_item_id,
                )
                .distinct()
            )
        if assistant_type:
            stmt = stmt.where(EvaluationCaseResult.assistant_type == assistant_type)
        if evaluation_run_id:
            stmt = stmt.where(EvaluationCaseResult.evaluation_run_id == evaluation_run_id)
        if human_root_cause:
            stmt = stmt.where(EvaluationCaseAnnotation.human_root_cause == HumanRootCause(human_root_cause))
        if human_fix_type:
            stmt = stmt.where(EvaluationCaseAnnotation.human_fix_type == HumanFixType(human_fix_type))
        if handling_status:
            stmt = stmt.where(EvaluationCaseAnnotation.handling_status == HandlingStatus(handling_status))
        if date_from:
            stmt = stmt.where(EvaluationCaseAnnotation.annotated_at >= date_from)
        if date_to:
            stmt = stmt.where(EvaluationCaseAnnotation.annotated_at <= date_to)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    EvaluationCaseResult.case_id.ilike(pattern),
                    EvaluationCaseResult.query.ilike(pattern),
                    EvaluationCaseAnnotation.handling_notes.ilike(pattern),
                )
            )
        if improvement_item_id:
            stmt = stmt.where(EvaluationImprovementItemCaseResult.improvement_item_id == improvement_item_id)
        if improvement_status:
            stmt = stmt.where(EvaluationImprovementItem.status == EvaluationImprovementStatus(improvement_status))
        if regression_status:
            stmt = stmt.where(
                EvaluationImprovementItem.regression_status
                == EvaluationImprovementRegressionStatus(regression_status)
            )
        return stmt

    def _annotation_list_item(
        self,
        annotation: EvaluationCaseAnnotation,
        case_result: EvaluationCaseResult,
        run: EvaluationRun,
    ) -> dict:
        run_display = format_evaluation_run_display(run)
        return {
            "annotation_id": annotation.id,
            "evaluation_case_result_id": annotation.evaluation_case_result_id,
            "evaluation_run_id": case_result.evaluation_run_id,
            "case_id": case_result.case_id,
            "assistant_type": case_result.assistant_type,
            "query": case_result.query,
            "human_judgement": annotation.human_judgement.value,
            "human_root_cause": annotation.human_root_cause.value,
            "human_fix_type": annotation.human_fix_type.value,
            "handling_status": annotation.handling_status.value,
            "handling_notes": annotation.handling_notes,
            "annotated_by": annotation.annotated_by,
            "annotated_at": annotation.annotated_at,
            "updated_at": annotation.updated_at,
            "system_failure_reason": case_result.failure_reason,
            "system_suggested_fix_type": case_result.suggested_fix_type,
            "evaluation_run_display_label": run_display["display_label"],
            "evaluation_run_change_type": run_display["change_type"],
            "evaluation_run_mode_summary": run_display["mode_summary"],
            "case_passed": case_result.passed,
            "related_improvement_items": self._related_improvement_items(case_result.id),
        }

    def _related_improvement_items(self, case_result_id: UUID) -> list[dict]:
        rows = self.db.execute(
            select(EvaluationImprovementItem, EvaluationImprovementItemCaseResult)
            .join(
                EvaluationImprovementItemCaseResult,
                EvaluationImprovementItemCaseResult.improvement_item_id == EvaluationImprovementItem.id,
            )
            .where(EvaluationImprovementItemCaseResult.evaluation_case_result_id == case_result_id)
            .order_by(EvaluationImprovementItem.created_at.desc())
        ).all()
        return [
            {
                "id": item.id,
                "fix_type": item.fix_type,
                "priority": item.priority.value,
                "status": item.status.value,
                "regression_status": item.regression_status.value,
                "suggested_action": item.suggested_action,
                "relation_source": link.relation_source.value,
            }
            for item, link in rows
        ]

    def _require_case_result(self, case_result_id: UUID) -> EvaluationCaseResult:
        record = self.db.get(EvaluationCaseResult, case_result_id)
        if not record:
            raise KeyError("Evaluation case result not found")
        return record

    def _annotation_for_case(self, case_result_id: UUID) -> EvaluationCaseAnnotation | None:
        return self.db.scalar(
            select(EvaluationCaseAnnotation).where(
                EvaluationCaseAnnotation.evaluation_case_result_id == case_result_id
            )
        )

    @staticmethod
    def _apply_values(
        annotation: EvaluationCaseAnnotation,
        user: User,
        human_judgement: str | None,
        human_root_cause: str | None,
        human_fix_type: str | None,
        handling_status: str | None,
        handling_notes: str | None,
        update_notes: bool,
    ) -> None:
        if human_judgement is not None:
            annotation.human_judgement = HumanJudgement(human_judgement)
        if human_root_cause is not None:
            annotation.human_root_cause = HumanRootCause(human_root_cause)
        if human_fix_type is not None:
            annotation.human_fix_type = HumanFixType(human_fix_type)
        if handling_status is not None:
            annotation.handling_status = HandlingStatus(handling_status)
        if update_notes:
            annotation.handling_notes = handling_notes
        annotation.annotated_by = user.id
