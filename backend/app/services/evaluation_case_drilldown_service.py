from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_annotation import EvaluationCaseAnnotation
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


class EvaluationCaseDrilldownService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_case_result(self, case_result_id: UUID) -> dict:
        record = self.db.get(EvaluationCaseResult, case_result_id)
        if not record:
            raise KeyError("Evaluation case result not found")
        return self._record_payload(record)

    def compare_case(self, before_run_id: UUID, after_run_id: UUID, case_id: str) -> dict:
        before_run = self.db.get(EvaluationRun, before_run_id)
        after_run = self.db.get(EvaluationRun, after_run_id)
        if not before_run or not after_run:
            raise KeyError("Evaluation run not found")

        before = self._case_record(before_run_id, case_id)
        after = self._case_record(after_run_id, case_id)
        comparison = self._comparison(before, after)
        return {
            "case_id": case_id,
            "before_run": format_evaluation_run_display(before_run),
            "after_run": format_evaluation_run_display(after_run),
            "before": self._record_payload(before) if before else None,
            "after": self._record_payload(after) if after else None,
            "comparison": comparison,
            "diagnostic_hints": self._diagnostic_hints(before, after, comparison),
        }

    def _case_record(self, run_id: UUID, case_id: str) -> EvaluationCaseResult | None:
        return self.db.scalar(
            select(EvaluationCaseResult).where(
                EvaluationCaseResult.evaluation_run_id == run_id,
                EvaluationCaseResult.case_id == case_id,
            )
        )

    def _record_payload(self, record: EvaluationCaseResult) -> dict:
        return {
            "id": record.id,
            "case_result_id": record.id,
            "evaluation_run_id": record.evaluation_run_id,
            "case_id": record.case_id,
            "assistant_type": record.assistant_type,
            "query": record.query,
            "expected_document": record.expected_document,
            "expected_keywords": record.expected_keywords,
            "expected_metadata": record.expected_metadata,
            "should_have_answer": record.should_have_answer,
            "passed": record.passed,
            "failure_reason": record.failure_reason,
            "suggested_fix_type": record.suggested_fix_type,
            "answer_excerpt": record.answer_excerpt,
            "used_metadata_filter": record.used_metadata_filter,
            "use_rerank": record.use_rerank,
            "rerank_applied": record.rerank_applied,
            "citations": record.citations,
            "retrieved_results": record.retrieved_results,
            "annotation": self._annotation_payload(record.id),
            "created_at": record.created_at,
        }

    def _annotation_payload(self, case_result_id: UUID) -> dict | None:
        annotation = self.db.scalar(
            select(EvaluationCaseAnnotation).where(
                EvaluationCaseAnnotation.evaluation_case_result_id == case_result_id
            )
        )
        if annotation is None:
            return None
        return {
            "id": annotation.id,
            "evaluation_case_result_id": annotation.evaluation_case_result_id,
            "human_judgement": annotation.human_judgement.value,
            "human_root_cause": annotation.human_root_cause.value,
            "human_fix_type": annotation.human_fix_type.value,
            "handling_status": annotation.handling_status.value,
            "handling_notes": annotation.handling_notes,
            "annotated_by": annotation.annotated_by,
            "annotated_at": annotation.annotated_at,
            "updated_at": annotation.updated_at,
        }

    def _comparison(self, before: EvaluationCaseResult | None, after: EvaluationCaseResult | None) -> dict:
        if not before or not after:
            return {
                "status": "unavailable",
                "rank_changes": [],
                "metadata_filter_changed": False,
                "rerank_changed": False,
                "citation_changed": False,
                "failure_reason_changed": False,
                "expected_document_ranks": {"before": None, "after": None},
            }

        status = "unchanged_passed"
        if not before.passed and after.passed:
            status = "resolved"
        elif before.passed and not after.passed:
            status = "introduced_failure"
        elif not before.passed and not after.passed:
            status = "still_failed"

        before_rank = self._expected_document_rank(before)
        after_rank = self._expected_document_rank(after)
        return {
            "status": status,
            "rank_changes": [
                {
                    "expected_document": before.expected_document or after.expected_document,
                    "before_rank": before_rank,
                    "after_rank": after_rank,
                    "delta": (before_rank - after_rank) if before_rank and after_rank else None,
                }
            ],
            "metadata_filter_changed": before.used_metadata_filter != after.used_metadata_filter,
            "rerank_changed": before.use_rerank != after.use_rerank or before.rerank_applied != after.rerank_applied,
            "citation_changed": bool(before.citations) != bool(after.citations),
            "failure_reason_changed": before.failure_reason != after.failure_reason,
            "expected_document_ranks": {"before": before_rank, "after": after_rank},
        }

    @staticmethod
    def _expected_document_rank(record: EvaluationCaseResult) -> int | None:
        if not record.expected_document:
            return None
        expected = record.expected_document.lower()
        for item in record.retrieved_results or []:
            document_name = str(item.get("document_name") or "").lower()
            if expected in document_name:
                return int(item.get("rank") or 0) or None
        return None

    def _diagnostic_hints(
        self,
        before: EvaluationCaseResult | None,
        after: EvaluationCaseResult | None,
        comparison: dict,
    ) -> list[str]:
        if not before or not after:
            return ["该历史运行未保存详细快照，无法进行 drill-down；系统不会重新执行检索或 LLM 调用。"]

        hints: list[str] = []
        before_rank = comparison["expected_document_ranks"]["before"]
        after_rank = comparison["expected_document_ranks"]["after"]
        if after_rank == 1 and (before_rank is None or before_rank > 5):
            hints.append("检索召回明显改善，优先检查 metadata filter、document metadata 或向量检索配置。")
        if before_rank and after_rank and before_rank <= 5 and after_rank <= 5 and after_rank < before_rank:
            hints.append("排序改善，优先检查 rerank 或 chunk 相关性。")
        target = after if after else before
        if target and target.expected_keywords and not self._keywords_present(target):
            hints.append("期望关键词仍缺失，可能是 chunk 切片、表格解析或文档内容覆盖不足。")
        if after and after.retrieved_results and not after.citations:
            hints.append("检索结果存在但无 citation，优先检查 prompt 或 citation 输出逻辑。")
        if after and not after.should_have_answer and after.answer_excerpt:
            hints.append("should_have_answer=false 但有明确回答，优先检查 no-answer prompt 约束和置信度阈值。")
        if not hints:
            hints.append("未命中明确规则，请结合排名、metadata filter、rerank 状态和引用变化继续排查。")
        return hints

    @staticmethod
    def _keywords_present(record: EvaluationCaseResult) -> bool:
        if not record.expected_keywords:
            return True
        haystack = "\n".join(str(item.get("chunk_excerpt") or "") for item in record.retrieved_results).lower()
        return all(str(keyword).lower() in haystack for keyword in record.expected_keywords)
