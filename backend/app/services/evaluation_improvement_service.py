from collections import Counter, defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_improvement import (
    EvaluationImprovementItem,
    EvaluationImprovementItemCaseResult,
    EvaluationImprovementPriority,
    EvaluationImprovementRelationSource,
    EvaluationImprovementRegressionStatus,
    EvaluationImprovementStatus,
)
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.user import User
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


ACTION_BY_FIX_TYPE = {
    "prompt": (
        "强化回答必须引用来源、资料不足时拒答、不得编造标准、参数、故障原因、供应商或替代料。"
    ),
    "metadata_filter": (
        "检查 query metadata extractor、Qdrant payload、metadata filter 合并逻辑，以及字段值是否标准化。"
    ),
    "rerank": "调整 rerank_top_n，检查 rerank score，并对比 rerank 前后排序。",
    "chunking": "检查 chunk 是否切断表格、步骤或关键字段，必要时调整 chunk size / overlap 或结构化 chunk。",
    "document_metadata": "补全文档 metadata，并标准化 equipment_model、fault_code、material_code、sop_code。",
    "test_case": "修正 eval_cases.json，确认 expected_document、expected_keywords 和 expected_metadata 是否合理。",
    "unknown": "人工检查该组失败用例，确认失败原因和修复方向。",
}

HUMAN_FIX_TYPE_MAP = {
    "update_prompt": "prompt",
    "update_metadata": "document_metadata",
    "update_chunking": "chunking",
    "tune_rerank": "rerank",
    "improve_parser": "chunking",
    "supplement_document": "document_metadata",
    "revise_eval_case": "test_case",
    "confirm_business_rule": "test_case",
    "no_action": "unknown",
}


class EvaluationImprovementService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summarize_failed_cases(self, evaluation_run_id: UUID) -> dict:
        run = self._get_assistant_run(evaluation_run_id)
        failed_cases = run.failed_cases or []
        return {
            "evaluation_run_id": evaluation_run_id,
            "total_failed_cases": len(failed_cases),
            "by_fix_type": self.group_by_suggested_fix_type(failed_cases),
            "by_assistant_type": self.group_by_assistant_type(failed_cases),
        }

    @staticmethod
    def group_by_suggested_fix_type(failed_cases: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for failed_case in failed_cases:
            grouped[str(failed_case.get("suggested_fix_type") or "unknown")].append(failed_case)
        return dict(grouped)

    @staticmethod
    def group_by_assistant_type(failed_cases: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for failed_case in failed_cases:
            grouped[str(failed_case.get("assistant_type") or "unknown")].append(failed_case)
        return dict(grouped)

    @staticmethod
    def calculate_fix_priority(group: list[dict]) -> EvaluationImprovementPriority:
        count = len(group)
        reasons = {str(item.get("failure_reason") or "unknown") for item in group}
        if count >= 3:
            return EvaluationImprovementPriority.high
        if reasons & {"hallucinated_answer", "answered_should_no_answer"}:
            return EvaluationImprovementPriority.high
        if count >= 2 or reasons & {"no_citation", "metadata_mismatch", "wrong_document_retrieved"}:
            return EvaluationImprovementPriority.medium
        return EvaluationImprovementPriority.low

    def generate_improvement_items(
        self,
        evaluation_run_id: UUID,
        user: User | None = None,
        force: bool = False,
    ) -> list[EvaluationImprovementItem]:
        run = self._get_assistant_run(evaluation_run_id)
        existing = list(
            self.db.scalars(
                select(EvaluationImprovementItem).where(
                    EvaluationImprovementItem.evaluation_run_id == evaluation_run_id
                )
            ).all()
        )
        if existing and not force:
            return existing
        if existing and force:
            self.db.execute(
                delete(EvaluationImprovementItemCaseResult).where(
                    EvaluationImprovementItemCaseResult.improvement_item_id.in_([item.id for item in existing])
                )
            )
            self.db.execute(
                delete(EvaluationImprovementItem).where(
                    EvaluationImprovementItem.evaluation_run_id == evaluation_run_id
                )
            )
            self.db.flush()

        failed_cases = run.failed_cases or []
        annotations = self._annotations_for_failed_cases(failed_cases)
        grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for failed_case in failed_cases:
            assistant_type = str(failed_case.get("assistant_type") or "unknown")
            annotation = self._annotation_for_failed_case(failed_case, annotations)
            fix_type = self._resolve_fix_type(failed_case, annotation)
            source = "human_annotation" if annotation else "system_rule"
            grouped[(assistant_type, fix_type, source)].append(failed_case)

        items: list[EvaluationImprovementItem] = []
        for (assistant_type, fix_type, source), group in sorted(grouped.items()):
            reasons = Counter(
                self._main_reason_for_item(item, annotations) for item in group
            )
            affected_case_ids = [str(item.get("id")) for item in group if item.get("id")]
            annotation_count = sum(1 for item in group if self._annotation_for_failed_case(item, annotations))
            item = EvaluationImprovementItem(
                evaluation_run_id=evaluation_run_id,
                assistant_type=assistant_type,
                fix_type=fix_type,
                priority=self.calculate_fix_priority(group),
                failed_case_count=len(group),
                affected_case_ids=affected_case_ids,
                main_failure_reasons=[reason for reason, _ in reasons.most_common(5)],
                suggested_action=ACTION_BY_FIX_TYPE.get(fix_type, ACTION_BY_FIX_TYPE["unknown"]),
                source=source,
                annotation_count=annotation_count,
                status=EvaluationImprovementStatus.open,
            )
            self.db.add(item)
            self.db.flush()
            self._link_item_to_case_results(item, group, annotations)
            items.append(item)
        self.db.commit()
        for item in items:
            self.db.refresh(item)
        return items

    def list_items(
        self,
        assistant_type: str | None = None,
        fix_type: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> list[EvaluationImprovementItem]:
        stmt = select(EvaluationImprovementItem).order_by(
            EvaluationImprovementItem.created_at.desc(), EvaluationImprovementItem.priority.asc()
        )
        if assistant_type:
            stmt = stmt.where(EvaluationImprovementItem.assistant_type == assistant_type)
        if fix_type:
            stmt = stmt.where(EvaluationImprovementItem.fix_type == fix_type)
        if status:
            stmt = stmt.where(EvaluationImprovementItem.status == EvaluationImprovementStatus(status))
        if priority:
            stmt = stmt.where(EvaluationImprovementItem.priority == EvaluationImprovementPriority(priority))
        return list(self.db.scalars(stmt).all())

    def update_item(
        self,
        item_id: UUID,
        user: User,
        status: str | None = None,
        suggested_action: str | None = None,
        resolved_evaluation_run_id: UUID | None = None,
    ) -> EvaluationImprovementItem:
        item = self.db.get(EvaluationImprovementItem, item_id)
        if not item:
            raise KeyError("Improvement item not found")
        if suggested_action is not None:
            item.suggested_action = suggested_action
        if resolved_evaluation_run_id is not None:
            item.resolved_evaluation_run_id = resolved_evaluation_run_id
        if status is not None:
            item.status = EvaluationImprovementStatus(status)
            if item.status in {EvaluationImprovementStatus.resolved, EvaluationImprovementStatus.ignored}:
                item.resolved_at = datetime.now(UTC)
                item.resolved_by = user.id
            else:
                item.resolved_at = None
                item.resolved_by = None
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_item_detail(self, item_id: UUID) -> dict:
        item = self.db.get(EvaluationImprovementItem, item_id)
        if not item:
            raise KeyError("Improvement item not found")
        return {
            **self._item_dict(item),
            "related_case_results": self._related_case_results(item_id),
            "related_annotations": self.annotations_for_item(item_id)["items"],
        }

    def annotations_for_item(self, item_id: UUID, page: int = 1, page_size: int = 20) -> dict:
        item = self.db.get(EvaluationImprovementItem, item_id)
        if not item:
            raise KeyError("Improvement item not found")
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        stmt = (
            select(
                EvaluationCaseAnnotation,
                EvaluationCaseResult,
                EvaluationRun,
                EvaluationImprovementItemCaseResult,
            )
            .join(
                EvaluationImprovementItemCaseResult,
                EvaluationImprovementItemCaseResult.evaluation_case_result_id
                == EvaluationCaseAnnotation.evaluation_case_result_id,
            )
            .join(EvaluationCaseResult, EvaluationCaseResult.id == EvaluationCaseAnnotation.evaluation_case_result_id)
            .join(EvaluationRun, EvaluationRun.id == EvaluationCaseResult.evaluation_run_id)
            .where(EvaluationImprovementItemCaseResult.improvement_item_id == item_id)
            .order_by(EvaluationCaseAnnotation.annotated_at.desc())
        )
        total = len(self.db.execute(stmt).all())
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        items = [
            self._annotation_detail(annotation, case_result, run, link.relation_source.value)
            for annotation, case_result, run, link in rows
        ]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total else 0,
        }

    def summary(self) -> dict:
        items = list(self.db.scalars(select(EvaluationImprovementItem)).all())
        open_items = [item for item in items if item.status == EvaluationImprovementStatus.open]
        reason_counter: Counter[str] = Counter()
        for item in open_items:
            reason_counter.update(item.main_failure_reasons or [])
        return {
            "total_open": len(open_items),
            "by_fix_type": dict(Counter(item.fix_type for item in open_items)),
            "by_assistant_type": dict(Counter(item.assistant_type for item in open_items)),
            "by_priority": dict(Counter(item.priority.value for item in open_items)),
            "top_failure_reasons": dict(reason_counter.most_common(10)),
        }

    def _link_item_to_case_results(
        self,
        item: EvaluationImprovementItem,
        failed_cases: list[dict],
        annotations: dict[UUID, EvaluationCaseAnnotation],
    ) -> None:
        seen: set[UUID] = set()
        for failed_case in failed_cases:
            case_result_id = self._case_result_id_for_failed_case(failed_case)
            if not case_result_id or case_result_id in seen:
                continue
            seen.add(case_result_id)
            relation_source = (
                EvaluationImprovementRelationSource.human_annotation
                if case_result_id in annotations
                else EvaluationImprovementRelationSource.system_rule
            )
            existing = self.db.scalar(
                select(EvaluationImprovementItemCaseResult).where(
                    EvaluationImprovementItemCaseResult.improvement_item_id == item.id,
                    EvaluationImprovementItemCaseResult.evaluation_case_result_id == case_result_id,
                )
            )
            if existing:
                existing.relation_source = relation_source
                continue
            self.db.add(
                EvaluationImprovementItemCaseResult(
                    improvement_item_id=item.id,
                    evaluation_case_result_id=case_result_id,
                    relation_source=relation_source,
                )
            )

    @staticmethod
    def _case_result_id_for_failed_case(failed_case: dict) -> UUID | None:
        value = failed_case.get("case_result_id")
        if not value:
            return None
        try:
            return UUID(str(value))
        except ValueError:
            return None

    def _related_case_results(self, item_id: UUID) -> list[dict]:
        rows = self.db.execute(
            select(EvaluationImprovementItemCaseResult, EvaluationCaseResult, EvaluationRun)
            .join(EvaluationCaseResult, EvaluationCaseResult.id == EvaluationImprovementItemCaseResult.evaluation_case_result_id)
            .join(EvaluationRun, EvaluationRun.id == EvaluationCaseResult.evaluation_run_id)
            .where(EvaluationImprovementItemCaseResult.improvement_item_id == item_id)
            .order_by(EvaluationCaseResult.case_id.asc())
        ).all()
        return [
            {
                "evaluation_case_result_id": case_result.id,
                "evaluation_run_id": case_result.evaluation_run_id,
                "case_id": case_result.case_id,
                "assistant_type": case_result.assistant_type,
                "query": case_result.query,
                "system_failure_reason": case_result.failure_reason,
                "system_suggested_fix_type": case_result.suggested_fix_type,
                "evaluation_run_display_label": format_evaluation_run_display(run)["display_label"],
                "evaluation_run_change_type": format_evaluation_run_display(run)["change_type"],
                "evaluation_run_mode_summary": format_evaluation_run_display(run)["mode_summary"],
                "case_passed": case_result.passed,
                "relation_source": link.relation_source.value,
            }
            for link, case_result, run in rows
        ]

    @staticmethod
    def _item_dict(item: EvaluationImprovementItem) -> dict:
        return {
            "id": item.id,
            "evaluation_run_id": item.evaluation_run_id,
            "assistant_type": item.assistant_type,
            "fix_type": item.fix_type,
            "priority": item.priority.value,
            "failed_case_count": item.failed_case_count,
            "affected_case_ids": item.affected_case_ids,
            "main_failure_reasons": item.main_failure_reasons,
            "suggested_action": item.suggested_action,
            "source": item.source,
            "annotation_count": item.annotation_count,
            "status": item.status.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "resolved_at": item.resolved_at,
            "resolved_by": item.resolved_by,
            "resolved_evaluation_run_id": item.resolved_evaluation_run_id,
            "regression_status": item.regression_status.value,
            "related_regression_id": item.related_regression_id,
        }

    @staticmethod
    def _annotation_detail(
        annotation: EvaluationCaseAnnotation,
        case_result: EvaluationCaseResult,
        run: EvaluationRun,
        relation_source: str,
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
            "relation_source": relation_source,
        }

    def _get_assistant_run(self, evaluation_run_id: UUID) -> EvaluationRun:
        run = self.db.get(EvaluationRun, evaluation_run_id)
        if not run or run.eval_type != EvaluationType.assistant:
            raise KeyError("Assistant evaluation run not found")
        return run

    def _annotations_for_failed_cases(self, failed_cases: list[dict]) -> dict[UUID, EvaluationCaseAnnotation]:
        case_result_ids: list[UUID] = []
        for failed_case in failed_cases:
            value = failed_case.get("case_result_id")
            if not value:
                continue
            try:
                case_result_ids.append(UUID(str(value)))
            except ValueError:
                continue
        if not case_result_ids:
            return {}
        annotations = self.db.scalars(
            select(EvaluationCaseAnnotation).where(
                EvaluationCaseAnnotation.evaluation_case_result_id.in_(case_result_ids)
            )
        ).all()
        return {annotation.evaluation_case_result_id: annotation for annotation in annotations}

    @staticmethod
    def _annotation_for_failed_case(
        failed_case: dict,
        annotations: dict[UUID, EvaluationCaseAnnotation],
    ) -> EvaluationCaseAnnotation | None:
        value = failed_case.get("case_result_id")
        if not value:
            return None
        try:
            return annotations.get(UUID(str(value)))
        except ValueError:
            return None

    @staticmethod
    def _main_reason_for_item(
        failed_case: dict,
        annotations: dict[UUID, EvaluationCaseAnnotation],
    ) -> str:
        annotation = EvaluationImprovementService._annotation_for_failed_case(failed_case, annotations)
        if annotation:
            return annotation.human_root_cause.value
        return str(failed_case.get("failure_reason") or "unknown")

    @staticmethod
    def _resolve_fix_type(failed_case: dict, annotation: EvaluationCaseAnnotation | None = None) -> str:
        if annotation:
            root_cause = annotation.human_root_cause.value
            if root_cause in ACTION_BY_FIX_TYPE:
                return root_cause
            return HUMAN_FIX_TYPE_MAP.get(annotation.human_fix_type.value, "unknown")
        fix_type = str(failed_case.get("suggested_fix_type") or "unknown")
        reason = str(failed_case.get("failure_reason") or "unknown")
        if reason == "metadata_mismatch":
            return "document_metadata"
        if reason == "wrong_document_retrieved" and failed_case.get("expected_metadata"):
            return "metadata_filter"
        if reason == "keyword_missing":
            return "chunking"
        if reason in {"low_mrr", "low_hit_at_k"}:
            return "rerank"
        if fix_type not in ACTION_BY_FIX_TYPE:
            return "unknown"
        return fix_type
