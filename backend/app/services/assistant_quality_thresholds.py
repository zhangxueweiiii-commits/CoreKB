from typing import Any

from app.schemas.evaluation import AssistantEvaluationMetrics


ASSISTANT_QUALITY_THRESHOLDS: dict[str, dict[str, float]] = {
    "maintenance": {
        "hit_at_3": 0.85,
        "mrr": 0.75,
        "citation_rate": 0.95,
        "no_answer_accuracy": 0.85,
    },
    "quality": {
        "hit_at_3": 0.85,
        "mrr": 0.75,
        "citation_rate": 1.0,
        "no_answer_accuracy": 0.9,
    },
    "sop": {
        "hit_at_3": 0.85,
        "mrr": 0.75,
        "citation_rate": 0.95,
        "no_answer_accuracy": 0.85,
    },
    "material": {
        "hit_at_3": 0.85,
        "mrr": 0.75,
        "citation_rate": 0.95,
        "metadata_match_rate": 0.85,
    },
}


def get_assistant_quality_thresholds() -> dict[str, dict[str, float]]:
    return ASSISTANT_QUALITY_THRESHOLDS


def evaluate_quality_gate(
    assistant_type: str,
    metrics: AssistantEvaluationMetrics,
) -> dict[str, Any]:
    threshold_config = ASSISTANT_QUALITY_THRESHOLDS.get(assistant_type, {})
    failed_thresholds = []
    for metric, required in threshold_config.items():
        actual = float(getattr(metrics, metric, 0.0))
        if actual < required:
            failed_thresholds.append({"metric": metric, "actual": actual, "required": required})
    return {
        "assistant_type": assistant_type,
        "quality_gate_passed": not failed_thresholds,
        "failed_thresholds": failed_thresholds,
        "threshold_config": threshold_config,
    }
