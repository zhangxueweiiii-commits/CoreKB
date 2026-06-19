from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_run import EvaluationRun
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


NUMERIC_COMPARE_METRICS = [
    "hit_at_1",
    "hit_at_3",
    "hit_at_5",
    "mrr",
    "keyword_match_rate",
    "metadata_match_rate",
    "citation_rate",
    "no_answer_accuracy",
]


class EvaluationRunCompareService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def compare_evaluation_runs(self, before_run_id: UUID, after_run_id: UUID) -> dict:
        before_run = self._get_run(before_run_id)
        after_run = self._get_run(after_run_id)
        comparable, warnings = self.check_runs_comparable(before_run, after_run)
        before_metrics = self._overall_metrics(before_run)
        after_metrics = self._overall_metrics(after_run)
        return {
            "before_run": format_evaluation_run_display(before_run),
            "after_run": format_evaluation_run_display(after_run),
            "comparable": comparable,
            "comparability_warnings": warnings,
            "metric_deltas": self.calculate_metrics_diff(before_metrics, after_metrics),
            "failed_case_diff": self.compare_failed_cases(before_run, after_run),
        }

    def _get_run(self, run_id: UUID) -> EvaluationRun:
        run = self.db.get(EvaluationRun, run_id)
        if not run:
            raise KeyError("Evaluation run not found")
        return run

    @staticmethod
    def calculate_metrics_diff(before_metrics: dict, after_metrics: dict) -> dict[str, float]:
        deltas: dict[str, float] = {}
        for metric in NUMERIC_COMPARE_METRICS:
            if metric not in before_metrics and metric not in after_metrics:
                continue
            before_value = float(before_metrics.get(metric, 0.0) or 0.0)
            after_value = float(after_metrics.get(metric, 0.0) or 0.0)
            deltas[metric] = after_value - before_value
        return deltas

    def compare_failed_cases(self, before_run: EvaluationRun, after_run: EvaluationRun) -> dict:
        before_failed = self._failed_case_map(before_run.failed_cases or [])
        after_failed = self._failed_case_map(after_run.failed_cases or [])
        before_ids = set(before_failed)
        after_ids = set(after_failed)
        resolved_ids = sorted(before_ids - after_ids)
        introduced_ids = sorted(after_ids - before_ids)
        still_failed_ids = sorted(before_ids & after_ids)

        all_case_ids = self._case_ids_for_count(before_run, after_run)
        unchanged_passed_count = max(len(all_case_ids - (before_ids | after_ids)), 0)

        return {
            "resolved_cases": [
                self._case_diff_item(case_id, before_failed.get(case_id), after_failed.get(case_id))
                for case_id in resolved_ids
            ],
            "introduced_failures": [
                self._case_diff_item(case_id, before_failed.get(case_id), after_failed.get(case_id))
                for case_id in introduced_ids
            ],
            "still_failed_cases": [
                self._case_diff_item(case_id, before_failed.get(case_id), after_failed.get(case_id))
                for case_id in still_failed_ids
            ],
            "unchanged_passed_count": unchanged_passed_count,
            "before_failed_count": len(before_failed),
            "after_failed_count": len(after_failed),
        }

    @staticmethod
    def check_runs_comparable(before_run: EvaluationRun, after_run: EvaluationRun) -> tuple[bool, list[str]]:
        before_config = before_run.config_snapshot or {}
        after_config = after_run.config_snapshot or {}
        warnings: list[str] = []
        comparable = True

        if before_run.eval_type != after_run.eval_type:
            warnings.append("eval_type 不一致")
            comparable = False
        if sorted(before_config.get("assistant_types") or []) != sorted(after_config.get("assistant_types") or []):
            warnings.append("assistant_types 不一致")
            comparable = False
        before_signature = before_config.get("evaluation_case_set_signature")
        after_signature = after_config.get("evaluation_case_set_signature")
        if not before_signature or not after_signature:
            warnings.append("evaluation_case_set_signature 缺失")
            comparable = False
        elif before_signature != after_signature:
            warnings.append("evaluation_case_set_signature 不一致")
            comparable = False

        config_changed = False
        if before_config.get("use_metadata_filter") != after_config.get("use_metadata_filter"):
            warnings.append("use_metadata_filter 不一致")
            config_changed = True
        if before_config.get("use_rerank") != after_config.get("use_rerank"):
            warnings.append("use_rerank 不一致")
            config_changed = True
        if before_config.get("rerank_top_n") != after_config.get("rerank_top_n"):
            warnings.append("rerank_top_n 不一致")
            config_changed = True
        if config_changed:
            warnings.append(
                "当前比较包含检索配置变化，指标变化可能来自 metadata filter 或 rerank，而非单一 prompt 或资料修改。"
            )
        return comparable, warnings

    @staticmethod
    def _overall_metrics(run: EvaluationRun) -> dict:
        metrics = run.metrics or {}
        return metrics.get("overall_metrics") or metrics

    @staticmethod
    def _failed_case_map(failed_cases: list[dict]) -> dict[str, dict]:
        return {str(item.get("id")): item for item in failed_cases if item.get("id")}

    @staticmethod
    def _case_ids_for_count(before_run: EvaluationRun, after_run: EvaluationRun) -> set[str]:
        before_ids = set((before_run.config_snapshot or {}).get("evaluation_case_ids") or [])
        after_ids = set((after_run.config_snapshot or {}).get("evaluation_case_ids") or [])
        if before_ids and after_ids:
            return before_ids & after_ids
        failed_ids = {
            str(item.get("id"))
            for item in (before_run.failed_cases or []) + (after_run.failed_cases or [])
            if item.get("id")
        }
        total = min(before_run.total_cases or 0, after_run.total_cases or 0)
        return failed_ids | {f"__passed_{index}" for index in range(max(total - len(failed_ids), 0))}

    def _case_diff_item(self, case_id: str, before: dict | None, after: dict | None) -> dict:
        source = after or before or {}
        annotation = self._annotation_summary(
            (after or {}).get("case_result_id") or (before or {}).get("case_result_id")
        )
        return {
            "case_id": case_id,
            "before_case_result_id": (before or {}).get("case_result_id"),
            "after_case_result_id": (after or {}).get("case_result_id"),
            "assistant_type": source.get("assistant_type"),
            "query": source.get("query"),
            "failure_reason": source.get("failure_reason") or source.get("reason"),
            "suggested_fix_type": source.get("suggested_fix_type"),
            "before_actual_top_documents": EvaluationRunCompareService._actual_top_documents(before),
            "after_actual_top_documents": EvaluationRunCompareService._actual_top_documents(after),
            "before_used_metadata_filter": (before or {}).get("used_metadata_filter") or {},
            "after_used_metadata_filter": (after or {}).get("used_metadata_filter") or {},
            "before": before,
            "after": after,
            "annotation_status": "已标注" if annotation else "未标注",
            "annotation": annotation,
        }

    def _annotation_summary(self, case_result_id: str | None) -> dict | None:
        if not case_result_id:
            return None
        try:
            annotation = self.db.scalar(
                select(EvaluationCaseAnnotation).where(
                    EvaluationCaseAnnotation.evaluation_case_result_id == UUID(str(case_result_id))
                )
            )
        except ValueError:
            return None
        if not annotation:
            return None
        return {
            "id": annotation.id,
            "human_root_cause": annotation.human_root_cause.value,
            "human_fix_type": annotation.human_fix_type.value,
            "handling_status": annotation.handling_status.value,
        }

    @staticmethod
    def _actual_top_documents(item: dict | None) -> list[str]:
        if not item:
            return []
        if item.get("actual_top_documents"):
            return list(item.get("actual_top_documents") or [])
        return [
            str(result.get("filename"))
            for result in (item.get("top_results") or [])
            if result.get("filename")
        ]
