from enum import StrEnum
from typing import Any

from app.schemas.evaluation import AssistantEvaluationCaseResult, EvalCase


class AssistantFailureReason(StrEnum):
    document_not_found = "document_not_found"
    wrong_document_retrieved = "wrong_document_retrieved"
    metadata_mismatch = "metadata_mismatch"
    keyword_missing = "keyword_missing"
    no_citation = "no_citation"
    hallucinated_answer = "hallucinated_answer"
    no_answer_should_answer = "no_answer_should_answer"
    answered_should_no_answer = "answered_should_no_answer"
    low_mrr = "low_mrr"
    low_hit_at_k = "low_hit_at_k"
    unknown = "unknown"


class SuggestedFixType(StrEnum):
    prompt = "prompt"
    metadata_filter = "metadata_filter"
    rerank = "rerank"
    chunking = "chunking"
    document_metadata = "document_metadata"
    test_case = "test_case"
    unknown = "unknown"


def analyze_failed_case(case: EvalCase, result: AssistantEvaluationCaseResult) -> dict[str, Any]:
    failure_reason = classify_failure_reason(case, result)
    return {
        "failure_reason": failure_reason,
        "failure_detail": _failure_detail(case, result, failure_reason),
        "suggested_fix_type": suggest_fix_type(failure_reason),
    }


def classify_failure_reason(case: EvalCase, result: AssistantEvaluationCaseResult) -> str:
    if not case.should_have_answer and result.no_answer_correct is False:
        return AssistantFailureReason.answered_should_no_answer.value

    if case.should_have_answer and not result.citation_present:
        return AssistantFailureReason.no_citation.value

    if case.should_have_answer and case.expected_document:
        actual_documents = [item.lower() for item in result.actual_top_documents]
        expected_document = case.expected_document.lower()
        if not actual_documents:
            return AssistantFailureReason.document_not_found.value
        if not any(expected_document in item for item in actual_documents):
            return AssistantFailureReason.wrong_document_retrieved.value

    if case.expected_metadata and result.metadata_match_rate < 1.0:
        return AssistantFailureReason.metadata_mismatch.value

    if case.expected_keywords and result.keyword_match_rate <= 0:
        return AssistantFailureReason.keyword_missing.value

    if case.should_have_answer and not result.hit_at_3:
        return AssistantFailureReason.low_hit_at_k.value

    if case.should_have_answer and not result.hit_at_1:
        return AssistantFailureReason.low_mrr.value

    return AssistantFailureReason.unknown.value


def suggest_fix_type(failure_reason: str) -> str:
    mapping = {
        AssistantFailureReason.document_not_found.value: SuggestedFixType.test_case.value,
        AssistantFailureReason.wrong_document_retrieved.value: SuggestedFixType.rerank.value,
        AssistantFailureReason.metadata_mismatch.value: SuggestedFixType.document_metadata.value,
        AssistantFailureReason.keyword_missing.value: SuggestedFixType.chunking.value,
        AssistantFailureReason.no_citation.value: SuggestedFixType.prompt.value,
        AssistantFailureReason.hallucinated_answer.value: SuggestedFixType.prompt.value,
        AssistantFailureReason.no_answer_should_answer.value: SuggestedFixType.prompt.value,
        AssistantFailureReason.answered_should_no_answer.value: SuggestedFixType.prompt.value,
        AssistantFailureReason.low_mrr.value: SuggestedFixType.rerank.value,
        AssistantFailureReason.low_hit_at_k.value: SuggestedFixType.metadata_filter.value,
    }
    return mapping.get(failure_reason, SuggestedFixType.unknown.value)


def _failure_detail(case: EvalCase, result: AssistantEvaluationCaseResult, failure_reason: str) -> str:
    if failure_reason == AssistantFailureReason.wrong_document_retrieved.value:
        return (
            f"Expected document '{case.expected_document}' was not in retrieved citations: "
            f"{', '.join(result.actual_top_documents) or 'none'}."
        )
    if failure_reason == AssistantFailureReason.metadata_mismatch.value:
        return (
            f"Expected metadata {case.expected_metadata} did not match used/retrieved metadata "
            f"{result.used_metadata_filter}."
        )
    if failure_reason == AssistantFailureReason.keyword_missing.value:
        return f"Expected keywords {case.expected_keywords} were not found in cited chunks."
    if failure_reason == AssistantFailureReason.no_citation.value:
        return "The assistant returned an answer without citations."
    if failure_reason == AssistantFailureReason.answered_should_no_answer.value:
        return "The case expected no reliable answer, but the assistant did not abstain."
    if failure_reason == AssistantFailureReason.document_not_found.value:
        return f"No cited document matched expected document '{case.expected_document}'."
    if failure_reason == AssistantFailureReason.low_hit_at_k.value:
        return "The expected document was not found within the required top-k range."
    if failure_reason == AssistantFailureReason.low_mrr.value:
        return "The expected document was retrieved, but not ranked high enough."
    return result.reason or "No specific rule matched this failed case."
