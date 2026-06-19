from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_improvement import (
    EvaluationImprovementItem,
    EvaluationImprovementRegressionStatus,
)
from app.models.evaluation_regression import EvaluationRegression
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


KEY_METRICS = [
    "hit_at_1",
    "hit_at_3",
    "mrr",
    "citation_rate",
    "no_answer_accuracy",
    "metadata_match_rate",
]


class EvaluationRegressionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_regression(
        self,
        before_run_id: UUID,
        after_run_id: UUID,
        improvement_item_ids: list[UUID],
        user: User,
        notes: str | None = None,
    ) -> EvaluationRegression:
        before_run = self._get_assistant_run(before_run_id)
        after_run = self._get_assistant_run(after_run_id)
        items = self._get_items(improvement_item_ids)
        if not items:
            raise ValueError("At least one improvement item is required")
        if any(item.evaluation_run_id != before_run_id for item in items):
            raise ValueError("All improvement items must belong to the before evaluation run")

        assistant_type = self._single_or_mixed([item.assistant_type for item in items])
        fix_type = self._single_or_mixed([item.fix_type for item in items])
        affected_case_ids = sorted({case_id for item in items for case_id in (item.affected_case_ids or [])})
        before_metrics = self._metrics_for_assistant(before_run, assistant_type)
        after_metrics = self._metrics_for_assistant(after_run, assistant_type)
        delta_metrics = self.calculate_metric_delta(before_metrics, after_metrics)
        resolved_case_ids, still_failed_case_ids = self.compare_failed_cases(
            before_failed_cases=before_run.failed_cases or [],
            after_failed_cases=after_run.failed_cases or [],
            affected_case_ids=affected_case_ids,
        )
        regression_passed = self.determine_regression_passed(delta_metrics, still_failed_case_ids, resolved_case_ids)

        regression = EvaluationRegression(
            before_evaluation_run_id=before_run_id,
            after_evaluation_run_id=after_run_id,
            improvement_item_ids=[str(item.id) for item in items],
            assistant_type=assistant_type,
            fix_type=fix_type,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            delta_metrics=delta_metrics,
            affected_case_ids=affected_case_ids,
            resolved_case_ids=resolved_case_ids,
            still_failed_case_ids=still_failed_case_ids,
            regression_passed=regression_passed,
            notes=notes,
            created_by=user.id,
        )
        self.db.add(regression)
        self.db.flush()

        regression_status = (
            EvaluationImprovementRegressionStatus.passed
            if regression_passed
            else EvaluationImprovementRegressionStatus.failed
        )
        for item in items:
            item.resolved_evaluation_run_id = after_run_id
            item.regression_status = regression_status
            item.related_regression_id = regression.id

        self.db.commit()
        self.db.refresh(regression)
        return self._attach_run_metadata(regression)

    @staticmethod
    def calculate_metric_delta(before_metrics: dict, after_metrics: dict) -> dict[str, float]:
        return {
            metric: float(after_metrics.get(metric, 0.0) or 0.0) - float(before_metrics.get(metric, 0.0) or 0.0)
            for metric in KEY_METRICS
        }

    @staticmethod
    def compare_failed_cases(
        before_failed_cases: list[dict],
        after_failed_cases: list[dict],
        affected_case_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        affected = set(affected_case_ids)
        before_failed = {str(item.get("id")) for item in before_failed_cases if item.get("id")}
        after_failed = {str(item.get("id")) for item in after_failed_cases if item.get("id")}
        relevant = affected & before_failed if affected else before_failed
        resolved_case_ids = sorted(relevant - after_failed)
        still_failed_case_ids = sorted(relevant & after_failed)
        return resolved_case_ids, still_failed_case_ids

    @staticmethod
    def determine_regression_passed(
        delta_metrics: dict[str, float],
        still_failed_case_ids: list[str],
        resolved_case_ids: list[str] | None = None,
    ) -> bool:
        if not resolved_case_ids:
            return False
        if delta_metrics.get("citation_rate", 0.0) < 0:
            return False
        if delta_metrics.get("no_answer_accuracy", 0.0) < -0.05:
            return False
        for metric in ("hit_at_1", "hit_at_3", "mrr", "metadata_match_rate"):
            if delta_metrics.get(metric, 0.0) < -0.03:
                return False
        return True

    def get_regression_summary(self) -> dict:
        regressions = list(
            self.db.scalars(select(EvaluationRegression).order_by(EvaluationRegression.created_at.desc())).all()
        )
        passed_count = sum(1 for regression in regressions if regression.regression_passed)
        failed_count = len(regressions) - passed_count
        return {
            "total_regressions": len(regressions),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "pass_rate": passed_count / len(regressions) if regressions else 0.0,
            "by_fix_type": dict(Counter(regression.fix_type for regression in regressions)),
            "by_assistant_type": dict(Counter(regression.assistant_type for regression in regressions)),
            "recent_regressions": [self._attach_run_metadata(regression) for regression in regressions[:10]],
        }

    def list_regressions(
        self,
        assistant_type: str | None = None,
        fix_type: str | None = None,
        regression_passed: bool | None = None,
        before_evaluation_run_id: UUID | None = None,
        after_evaluation_run_id: UUID | None = None,
    ) -> list[EvaluationRegression]:
        stmt = select(EvaluationRegression).order_by(EvaluationRegression.created_at.desc())
        if assistant_type:
            stmt = stmt.where(EvaluationRegression.assistant_type == assistant_type)
        if fix_type:
            stmt = stmt.where(EvaluationRegression.fix_type == fix_type)
        if regression_passed is not None:
            stmt = stmt.where(EvaluationRegression.regression_passed == regression_passed)
        if before_evaluation_run_id:
            stmt = stmt.where(EvaluationRegression.before_evaluation_run_id == before_evaluation_run_id)
        if after_evaluation_run_id:
            stmt = stmt.where(EvaluationRegression.after_evaluation_run_id == after_evaluation_run_id)
        return [self._attach_run_metadata(regression) for regression in self.db.scalars(stmt).all()]

    def get_regression(self, regression_id: UUID) -> EvaluationRegression | None:
        regression = self.db.get(EvaluationRegression, regression_id)
        return self._attach_run_metadata(regression) if regression else None

    def _get_assistant_run(self, run_id: UUID) -> EvaluationRun:
        run = self.db.get(EvaluationRun, run_id)
        if not run or run.eval_type != EvaluationType.assistant:
            raise KeyError("Assistant evaluation run not found")
        return run

    def _get_items(self, item_ids: list[UUID]) -> list[EvaluationImprovementItem]:
        if not item_ids:
            return []
        items = list(
            self.db.scalars(
                select(EvaluationImprovementItem).where(EvaluationImprovementItem.id.in_(item_ids))
            ).all()
        )
        if len(items) != len(set(item_ids)):
            raise KeyError("One or more improvement items were not found")
        return items

    @staticmethod
    def _single_or_mixed(values: list[str]) -> str:
        unique = sorted(set(values))
        return unique[0] if len(unique) == 1 else "mixed"

    @staticmethod
    def _metrics_for_assistant(run: EvaluationRun, assistant_type: str) -> dict:
        metrics = run.metrics or {}
        if assistant_type != "mixed":
            per_assistant = metrics.get("per_assistant_metrics") or {}
            if assistant_type in per_assistant:
                return per_assistant[assistant_type]
        return metrics.get("overall_metrics") or metrics

    def _attach_run_metadata(self, regression: EvaluationRegression) -> EvaluationRegression:
        before_run = self.db.get(EvaluationRun, regression.before_evaluation_run_id)
        after_run = self.db.get(EvaluationRun, regression.after_evaluation_run_id)
        before_display = format_evaluation_run_display(before_run) if before_run else None
        after_display = format_evaluation_run_display(after_run) if after_run else None
        regression.before_run_label = before_run.run_label if before_run else None
        regression.before_change_type = before_run.change_type if before_run else None
        regression.before_change_summary = before_run.change_summary if before_run else None
        regression.after_run_label = after_run.run_label if after_run else None
        regression.after_change_type = after_run.change_type if after_run else None
        regression.after_change_summary = after_run.change_summary if after_run else None
        regression.before_run_display = before_display
        regression.after_run_display = after_display
        regression.before_metrics_summary = before_display["metrics_summary"] if before_display else None
        regression.after_metrics_summary = after_display["metrics_summary"] if after_display else None
        regression.before_mode_summary = before_display["mode_summary"] if before_display else None
        regression.after_mode_summary = after_display["mode_summary"] if after_display else None
        regression.before_run = before_display
        regression.after_run = after_display
        return regression
