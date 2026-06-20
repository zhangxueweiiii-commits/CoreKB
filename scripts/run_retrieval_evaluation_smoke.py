from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.evaluation import EvalCase  # noqa: E402
from app.services.evaluation_service import EvaluationService  # noqa: E402
from app.services.retrieval_service import RetrievedChunk, RetrievalResultSet  # noqa: E402


DEFAULT_CASES_PATH = REPO_ROOT / "backend" / "tests" / "evaluation" / "fixtures" / "expected" / "eval_cases.json"


class DeterministicRetrieval:
    """Fake retrieval service for smoke testing evaluation logic without external services."""

    def __init__(self, cases: list[EvalCase]) -> None:
        self.cases_by_query = {case.query: case for case in cases}
        self.calls: list[dict[str, Any]] = []

    async def search_with_options(self, **kwargs: Any) -> RetrievalResultSet:
        self.calls.append(kwargs)
        case = self.cases_by_query[kwargs["query"]]
        if not case.should_have_answer:
            return RetrievalResultSet(results=[], use_rerank=bool(kwargs.get("use_rerank")))

        document_name = case.expected_document or f"{case.id}.txt"
        keywords = " ".join(case.expected_keywords) if case.expected_keywords else case.query
        metadata = dict(case.expected_metadata)
        metadata.setdefault("document_title", document_name)
        score = 0.95
        return RetrievalResultSet(
            results=[
                RetrievedChunk(
                    chunk_text=f"{document_name}\n{keywords}",
                    filename=f"{document_name}.txt",
                    page_number=None,
                    score=score,
                    document_id=uuid.uuid4(),
                    chunk_id=uuid.uuid4(),
                    metadata=metadata,
                    vector_score=score,
                    final_score=score,
                )
            ],
            use_rerank=bool(kwargs.get("use_rerank")),
            rerank_applied=False,
        )


def _metrics_dict(metrics: Any) -> dict[str, Any]:
    if hasattr(metrics, "model_dump"):
        return metrics.model_dump(mode="json")
    return dict(metrics)


def load_eval_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("eval cases file must contain a JSON array")
    return [EvalCase.model_validate(item) for item in data]


async def run_retrieval_smoke(
    cases_path: Path = DEFAULT_CASES_PATH,
    use_metadata_filter: bool = True,
    use_rerank: bool = False,
) -> dict[str, Any]:
    cases = load_eval_cases(cases_path)
    retrieval = DeterministicRetrieval(cases)
    service = EvaluationService(retrieval_service=retrieval, assistant_service=SimpleNamespace())
    dummy_user = SimpleNamespace(id=uuid.uuid4())
    kb_ids = [uuid.uuid4()]

    results = [
        await service.evaluate_case(
            db=None,
            user=dummy_user,
            case=case,
            knowledge_base_ids=kb_ids,
            use_metadata_filter=use_metadata_filter,
            use_rerank=use_rerank,
        )
        for case in cases
    ]
    metrics = service.calculate_metrics(
        results,
        use_metadata_filter=use_metadata_filter,
        use_rerank=use_rerank,
        mode="retrieval_smoke",
    )
    failed_cases = [result.model_dump(mode="json") for result in results if not result.passed]
    answerable_results = [result for result in results if result.should_have_answer]
    no_answer_results = [result for result in results if not result.should_have_answer]
    smoke_passed = not failed_cases and bool(results)

    return {
        "eval_type": "retrieval_smoke",
        "case_file": cases_path.as_posix(),
        "total_cases": len(results),
        "answerable_cases": len(answerable_results),
        "no_answer_cases": len(no_answer_results),
        "metrics": _metrics_dict(metrics),
        "failed_cases": failed_cases,
        "smoke_passed": smoke_passed,
        "metadata_filter_enabled": use_metadata_filter,
        "metadata_filter_used_cases": sum(1 for result in results if result.used_metadata_filter),
        "use_rerank": use_rerank,
        "rerank_applied_cases": sum(1 for result in results if result.rerank_applied),
        "retrieval_call_count": len(retrieval.calls),
        "case_result_persistence": False,
        "read_only": True,
        "runtime_dependencies": {
            "database": False,
            "qdrant": False,
            "redis": False,
            "celery": False,
            "embedding": False,
            "rerank_provider": False,
            "llm": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the read-only CoreKB retrieval evaluation smoke test")
    parser.add_argument("--cases", default=DEFAULT_CASES_PATH.as_posix(), help="Path to eval_cases.json")
    parser.add_argument("--no-metadata-filter", action="store_true", help="Disable expected metadata filter during smoke evaluation")
    parser.add_argument("--output", help="Optional path for writing the JSON summary")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cases_path = Path(args.cases)
    try:
        summary = asyncio.run(
            run_retrieval_smoke(
                cases_path=cases_path,
                use_metadata_filter=not args.no_metadata_filter,
            )
        )
    except Exception as exc:
        error_summary = {
            "eval_type": "retrieval_smoke",
            "case_file": cases_path.as_posix(),
            "smoke_passed": False,
            "error": str(exc),
            "read_only": True,
        }
        print(json.dumps(error_summary, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    output = json.dumps(summary, ensure_ascii=False, indent=indent)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if summary["smoke_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
