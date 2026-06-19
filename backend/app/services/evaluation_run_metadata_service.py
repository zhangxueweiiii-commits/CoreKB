import hashlib
import json
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.user import User


ALLOWED_EVALUATION_CHANGE_TYPES = {
    "prompt",
    "metadata",
    "chunking",
    "rerank",
    "eval_case",
    "parser",
    "mixed",
    "baseline",
    "unknown",
}


def validate_change_type(change_type: str | None) -> str:
    normalized = (change_type or "unknown").strip() or "unknown"
    if normalized not in ALLOWED_EVALUATION_CHANGE_TYPES:
        raise ValueError(f"Invalid change_type: {change_type}")
    return normalized


def build_evaluation_case_set_signature(cases: list) -> str:
    payload = [
        {
            "id": case.id,
            "assistant_type": case.assistant_type,
            "expected_document": case.expected_document,
            "should_have_answer": case.should_have_answer,
        }
        for case in cases
    ]
    payload.sort(key=lambda item: (str(item["id"]), str(item["assistant_type"] or "")))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_assistant_config_snapshot(
    use_metadata_filter: bool,
    use_rerank: bool,
    rerank_top_n: int | None,
    assistant_types: list[str],
    mode: str,
    evaluation_case_set_signature: str | None = None,
    evaluation_case_ids: list[str] | None = None,
) -> dict:
    return {
        "eval_type": EvaluationType.assistant.value,
        "use_metadata_filter": use_metadata_filter,
        "use_rerank": use_rerank,
        "rerank_top_n": rerank_top_n,
        "assistant_types": assistant_types,
        "mode": mode,
        "evaluation_case_set_signature": evaluation_case_set_signature,
        "evaluation_case_ids": evaluation_case_ids or [],
    }


def build_retrieval_config_snapshot(
    use_metadata_filter: bool,
    use_rerank: bool,
    rerank_top_n: int | None,
    mode: str,
    evaluation_case_set_signature: str | None = None,
    evaluation_case_ids: list[str] | None = None,
) -> dict:
    return {
        "eval_type": EvaluationType.retrieval.value,
        "assistant_types": [],
        "use_metadata_filter": use_metadata_filter,
        "use_rerank": use_rerank,
        "rerank_top_n": rerank_top_n,
        "mode": mode,
        "evaluation_case_set_signature": evaluation_case_set_signature,
        "evaluation_case_ids": evaluation_case_ids or [],
    }


def get_evaluation_mode_summary(run: EvaluationRun) -> str:
    metrics = run.metrics or {}
    config_snapshot = run.config_snapshot or {}
    use_metadata_filter = bool(metrics.get("use_metadata_filter", config_snapshot.get("use_metadata_filter", False)))
    use_rerank = bool(metrics.get("use_rerank", config_snapshot.get("use_rerank", False)))
    if not use_metadata_filter and not use_rerank:
        return "Baseline"
    if use_metadata_filter and not use_rerank:
        return "Metadata filter"
    if use_metadata_filter and use_rerank:
        return "Metadata filter + Rerank"
    return "Rerank only"


def get_evaluation_metrics_summary(run: EvaluationRun) -> dict:
    metrics = run.metrics or {}
    source = metrics.get("overall_metrics") or metrics
    return {
        "hit_at_1": source.get("hit_at_1"),
        "hit_at_3": source.get("hit_at_3"),
        "hit_at_5": source.get("hit_at_5"),
        "mrr": source.get("mrr"),
        "keyword_match_rate": source.get("keyword_match_rate"),
        "metadata_match_rate": source.get("metadata_match_rate"),
        "citation_rate": source.get("citation_rate"),
        "no_answer_accuracy": source.get("no_answer_accuracy"),
        "quality_gate_passed": source.get("quality_gate_passed", metrics.get("quality_gate_passed")),
    }


def format_evaluation_run_display(run: EvaluationRun) -> dict:
    label_source = run.run_label or run.change_type
    display_label = f"{label_source} · Run #{run.id}" if label_source else f"Run #{run.id}"
    return {
        "id": run.id,
        "display_label": display_label,
        "run_label": run.run_label,
        "change_type": run.change_type,
        "change_summary": run.change_summary,
        "operator_notes": run.operator_notes,
        "created_at": run.created_at,
        "created_by": run.created_by,
        "config_snapshot": run.config_snapshot,
        "metrics_summary": get_evaluation_metrics_summary(run),
        "mode_summary": get_evaluation_mode_summary(run),
    }


class EvaluationRunMetadataService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def update_metadata(
        self,
        run_id: UUID,
        user: User,
        run_label: str | None = None,
        change_type: str | None = None,
        change_summary: str | None = None,
        operator_notes: str | None = None,
    ) -> EvaluationRun:
        run = self.db.get(EvaluationRun, run_id)
        if not run:
            raise KeyError("Evaluation run not found")
        if run_label is not None:
            run.run_label = run_label
        if change_type is not None:
            run.change_type = validate_change_type(change_type)
        if change_summary is not None:
            run.change_summary = change_summary
        if operator_notes is not None:
            run.operator_notes = operator_notes
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_runs(
        self,
        eval_type: str | None = None,
        change_type: str | None = None,
        assistant_type: str | None = None,
        limit: int = 50,
        order_by: str = "created_at",
    ) -> list[dict]:
        order_columns = {
            "created_at": EvaluationRun.created_at,
            "run_label": EvaluationRun.run_label,
            "change_type": EvaluationRun.change_type,
        }
        if order_by not in order_columns:
            raise ValueError(f"Invalid order_by: {order_by}")
        order_expression = desc(order_columns[order_by]) if order_by == "created_at" else asc(order_columns[order_by])
        stmt = select(EvaluationRun).order_by(order_expression).limit(limit)
        if eval_type:
            stmt = stmt.where(EvaluationRun.eval_type == EvaluationType(eval_type))
        if change_type:
            stmt = stmt.where(EvaluationRun.change_type == validate_change_type(change_type))
        runs = list(self.db.scalars(stmt).all())
        if assistant_type:
            runs = [
                run
                for run in runs
                if assistant_type in ((run.metrics or {}).get("per_assistant_metrics") or {})
            ]
        return [
            {
                "id": run.id,
                "eval_type": run.eval_type,
                "total_cases": run.total_cases,
                "metrics": run.metrics,
                **format_evaluation_run_display(run),
            }
            for run in runs
        ]
