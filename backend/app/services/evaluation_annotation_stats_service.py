from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_annotation import EvaluationCaseAnnotation, HandlingStatus
from app.models.evaluation_run import EvaluationCaseResult


ROOT_CAUSE_LABELS = {
    "prompt": "提示词",
    "metadata_filter": "元数据过滤",
    "document_metadata": "文档元数据",
    "chunking": "切片",
    "rerank": "重排",
    "parser": "解析器",
    "source_document": "源文档",
    "evaluation_case": "评估用例",
    "business_rule": "业务规则",
    "unknown": "未知",
}

FIX_TYPE_LABELS = {
    "update_prompt": "更新提示词",
    "update_metadata": "补充元数据",
    "update_chunking": "调整切片",
    "tune_rerank": "调优重排",
    "improve_parser": "改进解析器",
    "supplement_document": "补充文档",
    "revise_eval_case": "修订评估用例",
    "confirm_business_rule": "确认业务规则",
    "no_action": "无需动作",
}

HANDLING_STATUS_LABELS = {
    "open": "待处理",
    "investigating": "排查中",
    "planned": "已计划",
    "resolved": "已解决",
    "ignored": "已忽略",
}

ASSISTANT_TYPE_LABELS = {
    "maintenance": "维修助手",
    "quality": "质量助手",
    "sop": "SOP 助手",
    "material": "物料 / 参数助手",
    "unknown": "未知助手",
}

RECOMMENDED_ACTIONS = {
    "document_metadata": "优先补充设备型号、故障码、物料编码、SOP 编号和版本等文档元数据。",
    "metadata_filter": "建议进入 metadata 半自动标注与审核流程，并检查字段标准化与过滤规则。",
    "chunking": "建议检查 SOP 步骤、Excel 表格、设备手册是否被错误切分。",
    "prompt": "建议检查引用强制、资料不足拒答、安全提示等岗位助手约束。",
    "rerank": "建议检查 rerank_top_n、候选召回数量和排序效果。",
    "source_document": "建议补充或更新源文件，而不是继续调模型参数。",
    "evaluation_case": "建议复核评估问题、标准答案和 expected metadata。",
    "parser": "建议检查文档解析器是否保留页码、表格结构、标题层级和关键字段。",
    "business_rule": "建议请业务专家确认判定规则，再决定是否调整评估用例或资料。",
    "unknown": "建议人工复核这批标注，先确认主要根因再进入修复流程。",
}


@dataclass(frozen=True)
class AnnotationStatsRecord:
    annotation: EvaluationCaseAnnotation
    assistant_type: str
    evaluation_run_id: UUID


class EvaluationAnnotationStatsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_annotation_summary(
        self,
        evaluation_run_id: UUID | None = None,
        assistant_type: str | None = None,
        handling_status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        records = self._load_records(
            evaluation_run_id=evaluation_run_id,
            assistant_type=assistant_type,
            handling_status=handling_status,
            date_from=date_from,
            date_to=date_to,
        )
        total = len(records)
        return {
            "total_annotations": total,
            "by_root_cause": self.group_by_root_cause(records, total),
            "by_fix_type": self.group_by_fix_type(records, total),
            "by_handling_status": self.group_by_handling_status(records),
            "by_assistant_type": self.group_by_assistant_type(records),
            "open_priority_items": self.get_open_priority_items(records),
        }

    def group_by_root_cause(self, records: list[AnnotationStatsRecord], total: int | None = None) -> list[dict]:
        total_count = len(records) if total is None else total
        counter = Counter(record.annotation.human_root_cause.value for record in records)
        return [
            {
                "key": key,
                "label": ROOT_CAUSE_LABELS.get(key, key),
                "count": count,
                "percentage": self._percentage(count, total_count),
                "recommended_action": self._recommended_action(key),
            }
            for key, count in counter.most_common()
        ]

    def group_by_fix_type(self, records: list[AnnotationStatsRecord], total: int | None = None) -> list[dict]:
        total_count = len(records) if total is None else total
        grouped: dict[str, list[AnnotationStatsRecord]] = {}
        for record in records:
            grouped.setdefault(record.annotation.human_fix_type.value, []).append(record)
        items = []
        for key, group in grouped.items():
            assistant_counts = Counter(record.assistant_type for record in group)
            items.append(
                {
                    "key": key,
                    "label": FIX_TYPE_LABELS.get(key, key),
                    "count": len(group),
                    "percentage": self._percentage(len(group), total_count),
                    "assistant_types": [
                        {
                            "key": assistant,
                            "label": ASSISTANT_TYPE_LABELS.get(assistant, assistant),
                            "count": count,
                        }
                        for assistant, count in assistant_counts.most_common()
                    ],
                }
            )
        return sorted(items, key=lambda item: (-item["count"], item["key"]))

    def group_by_handling_status(self, records: list[AnnotationStatsRecord]) -> list[dict]:
        counter = Counter(record.annotation.handling_status.value for record in records)
        return [
            {
                "key": key,
                "label": HANDLING_STATUS_LABELS.get(key, key),
                "count": count,
            }
            for key, count in counter.most_common()
        ]

    def group_by_assistant_type(self, records: list[AnnotationStatsRecord]) -> list[dict]:
        counter = Counter(record.assistant_type for record in records)
        return [
            {
                "key": key,
                "label": ASSISTANT_TYPE_LABELS.get(key, key),
                "count": count,
            }
            for key, count in counter.most_common()
        ]

    def get_open_priority_items(self, records: list[AnnotationStatsRecord]) -> list[dict]:
        open_records = [
            record
            for record in records
            if record.annotation.handling_status.value not in {HandlingStatus.resolved.value, HandlingStatus.ignored.value}
        ]
        grouped: Counter[tuple[str, str, str]] = Counter(
            (
                record.annotation.human_root_cause.value,
                record.annotation.human_fix_type.value,
                record.assistant_type,
            )
            for record in open_records
        )
        return [
            {
                "root_cause": root_cause,
                "fix_type": fix_type,
                "assistant_type": assistant_type,
                "count": count,
                "recommended_action": self._recommended_action(root_cause),
            }
            for (root_cause, fix_type, assistant_type), count in grouped.most_common()
        ]

    def _load_records(
        self,
        evaluation_run_id: UUID | None = None,
        assistant_type: str | None = None,
        handling_status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AnnotationStatsRecord]:
        stmt = select(
            EvaluationCaseAnnotation,
            EvaluationCaseResult.assistant_type,
            EvaluationCaseResult.evaluation_run_id,
        ).join(
            EvaluationCaseResult,
            EvaluationCaseResult.id == EvaluationCaseAnnotation.evaluation_case_result_id,
        )
        if evaluation_run_id:
            stmt = stmt.where(EvaluationCaseResult.evaluation_run_id == evaluation_run_id)
        if assistant_type:
            stmt = stmt.where(EvaluationCaseResult.assistant_type == assistant_type)
        if handling_status:
            stmt = stmt.where(EvaluationCaseAnnotation.handling_status == HandlingStatus(handling_status))
        if date_from:
            stmt = stmt.where(EvaluationCaseAnnotation.annotated_at >= date_from)
        if date_to:
            stmt = stmt.where(EvaluationCaseAnnotation.annotated_at <= date_to)
        rows = self.db.execute(stmt).all()
        return [
            AnnotationStatsRecord(
                annotation=annotation,
                assistant_type=assistant_type_value or "unknown",
                evaluation_run_id=run_id,
            )
            for annotation, assistant_type_value, run_id in rows
        ]

    @staticmethod
    def _percentage(count: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return count / total

    @staticmethod
    def _recommended_action(root_cause: str) -> str:
        return RECOMMENDED_ACTIONS.get(root_cause, RECOMMENDED_ACTIONS["unknown"])
