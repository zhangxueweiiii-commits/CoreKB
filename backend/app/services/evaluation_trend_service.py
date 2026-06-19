from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_regression import EvaluationRegression
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


TREND_METRICS = [
    "hit_at_1",
    "hit_at_3",
    "hit_at_5",
    "mrr",
    "keyword_match_rate",
    "metadata_match_rate",
    "no_answer_accuracy",
    "citation_rate",
]


class EvaluationTrendService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_assistant_metric_trends(
        self,
        assistant_type: str | None = None,
        metric: str | None = None,
        limit: int = 20,
        use_metadata_filter: bool | None = None,
        use_rerank: bool | None = None,
    ) -> dict:
        runs = self._assistant_runs(limit=limit * 4, use_metadata_filter=use_metadata_filter, use_rerank=use_rerank)
        items: list[dict] = []
        for run in runs:
            metrics = run.metrics or {}
            per_assistant = metrics.get("per_assistant_metrics") or {}
            for current_assistant_type, assistant_metrics in per_assistant.items():
                if assistant_type and current_assistant_type != assistant_type:
                    continue
                items.append(self._assistant_item(run, current_assistant_type, assistant_metrics))
        items = items[:limit]
        self._attach_warnings(items, metric=metric)
        delta = self.calculate_trend_delta(items[0], items[1], metric=metric) if len(items) >= 2 else {}
        return {
            "assistant_type": assistant_type or "all",
            "items": items,
            "delta_from_previous": delta,
            "regression_warnings": items[0].get("regression_warnings", []) if items else [],
        }

    def get_overall_metric_trends(
        self,
        limit: int = 20,
        metric: str | None = None,
        use_metadata_filter: bool | None = None,
        use_rerank: bool | None = None,
    ) -> dict:
        runs = self._assistant_runs(limit=limit, use_metadata_filter=use_metadata_filter, use_rerank=use_rerank)
        items = [self._overall_item(run, (run.metrics or {}).get("overall_metrics") or {}) for run in runs]
        self._attach_warnings(items, metric=metric)
        delta = self.calculate_trend_delta(items[0], items[1], metric=metric) if len(items) >= 2 else {}
        return {
            "items": items,
            "delta_from_previous": delta,
            "regression_warnings": items[0].get("regression_warnings", []) if items else [],
        }

    def get_regression_trends(self, limit: int = 20) -> dict:
        regressions = list(
            self.db.scalars(
                select(EvaluationRegression).order_by(EvaluationRegression.created_at.desc()).limit(limit)
            ).all()
        )
        total = self.db.scalar(select(EvaluationRegression)) is not None
        all_regressions = list(self.db.scalars(select(EvaluationRegression)).all()) if total else []
        passed_count = sum(1 for regression in all_regressions if regression.regression_passed)
        failed_count = len(all_regressions) - passed_count
        return {
            "total_regressions": len(all_regressions),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "pass_rate": passed_count / len(all_regressions) if all_regressions else 0.0,
            "recent_items": regressions,
        }

    @staticmethod
    def calculate_trend_delta(
        current: dict,
        previous: dict,
        metric: str | None = None,
    ) -> dict[str, float]:
        metrics = [metric] if metric else TREND_METRICS
        return {
            name: float(current.get(name, 0.0) or 0.0) - float(previous.get(name, 0.0) or 0.0)
            for name in metrics
            if name in TREND_METRICS
        }

    @staticmethod
    def detect_metric_regression(current: dict, previous: dict, metric: str | None = None) -> list[dict]:
        metrics = [metric] if metric else ["hit_at_1", "hit_at_3", "mrr", "citation_rate", "no_answer_accuracy"]
        warnings: list[dict] = []
        for name in metrics:
            if name not in TREND_METRICS:
                continue
            current_value = float(current.get(name, 0.0) or 0.0)
            previous_value = float(previous.get(name, 0.0) or 0.0)
            delta = current_value - previous_value
            threshold = 0.0 if name == "citation_rate" else -0.05
            if delta < threshold:
                warnings.append(
                    {
                        "metric": name,
                        "previous": previous_value,
                        "current": current_value,
                        "delta": delta,
                        "level": "warning",
                    }
                )
        if (
            not metric
            and previous.get("quality_gate_passed") is True
            and current.get("quality_gate_passed") is False
        ):
            warnings.append(
                {
                    "metric": "quality_gate_passed",
                    "previous": True,
                    "current": False,
                    "delta": None,
                    "level": "warning",
                }
            )
        return warnings

    def _assistant_runs(
        self,
        limit: int,
        use_metadata_filter: bool | None = None,
        use_rerank: bool | None = None,
    ) -> list[EvaluationRun]:
        runs = list(
            self.db.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.eval_type == EvaluationType.assistant)
                .order_by(EvaluationRun.created_at.desc())
                .limit(max(limit, 1) * 3)
            ).all()
        )
        filtered = []
        for run in runs:
            metrics = run.metrics or {}
            if use_metadata_filter is not None and bool(metrics.get("use_metadata_filter", True)) != use_metadata_filter:
                continue
            if use_rerank is not None and bool(metrics.get("use_rerank", True)) != use_rerank:
                continue
            filtered.append(run)
        return filtered[:limit]

    @staticmethod
    def _assistant_item(run: EvaluationRun, assistant_type: str, metrics: dict) -> dict:
        return {
            "evaluation_run_id": run.id,
            "created_at": run.created_at,
            "assistant_type": assistant_type,
            **EvaluationTrendService._run_metadata_projection(run),
            "mode": str((run.metrics or {}).get("mode", "single")),
            "use_metadata_filter": bool((run.metrics or {}).get("use_metadata_filter", True)),
            "use_rerank": bool((run.metrics or {}).get("use_rerank", True)),
            **EvaluationTrendService._metric_projection(metrics),
            "quality_gate_passed": bool(metrics.get("quality_gate_passed", True)),
            "regression_warnings": [],
        }

    @staticmethod
    def _overall_item(run: EvaluationRun, metrics: dict) -> dict:
        return {
            "evaluation_run_id": run.id,
            "created_at": run.created_at,
            **EvaluationTrendService._run_metadata_projection(run),
            "mode": str((run.metrics or {}).get("mode", "single")),
            "use_metadata_filter": bool((run.metrics or {}).get("use_metadata_filter", True)),
            "use_rerank": bool((run.metrics or {}).get("use_rerank", True)),
            **EvaluationTrendService._metric_projection(metrics),
            "quality_gate_passed": bool(metrics.get("quality_gate_passed", True)),
            "regression_warnings": [],
        }

    @staticmethod
    def _metric_projection(metrics: dict) -> dict[str, float]:
        return {name: float(metrics.get(name, 0.0) or 0.0) for name in TREND_METRICS}

    @staticmethod
    def _run_metadata_projection(run: EvaluationRun) -> dict:
        display = format_evaluation_run_display(run)
        return {
            "display_label": display["display_label"],
            "metrics_summary": display["metrics_summary"],
            "mode_summary": display["mode_summary"],
            "run_label": run.run_label,
            "change_type": run.change_type,
            "change_summary": run.change_summary,
            "operator_notes": run.operator_notes,
            "config_snapshot": run.config_snapshot,
        }

    @staticmethod
    def _attach_warnings(items: list[dict], metric: str | None = None) -> None:
        for index, item in enumerate(items):
            if index + 1 < len(items):
                item["regression_warnings"] = EvaluationTrendService.detect_metric_regression(
                    item,
                    items[index + 1],
                    metric=metric,
                )
