import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus
from app.models.evaluation_run import EvaluationCaseResult as EvaluationCaseResultRecord
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.evaluation import (
    EvalCase,
    EvalCaseResult,
    AssistantEvaluationCaseResult,
    AssistantEvaluationCompareResponse,
    AssistantEvaluationMetrics,
    AssistantEvaluationResponse,
    EvaluationMetrics,
    EvaluationReadiness,
    RetrievalEvaluationResponse,
    RetrievalEvaluationCompareResponse,
)
from app.schemas.assistant import AssistantChatRequest
from app.services.assistant_failure_analyzer import analyze_failed_case
from app.services.assistant_quality_thresholds import (
    evaluate_quality_gate,
    get_assistant_quality_thresholds,
)
from app.services.assistant_service import AssistantService
from app.services.evaluation_run_metadata_service import (
    build_assistant_config_snapshot,
    build_evaluation_case_set_signature,
    build_retrieval_config_snapshot,
    validate_change_type,
)
from app.services.query_metadata_extractor import extract_metadata_from_query, sanitize_metadata_filter
from app.services.retrieval_service import RetrievedChunk, RetrievalService


DEFAULT_EVAL_CASES_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "evaluation" / "fixtures" / "expected" / "eval_cases.json"
)


class EvaluationService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        assistant_service: AssistantService | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.assistant_service = assistant_service or AssistantService()

    def load_eval_cases(self, path: Path | None = None) -> list[EvalCase]:
        target = path or DEFAULT_EVAL_CASES_PATH
        data = json.loads(target.read_text(encoding="utf-8"))
        return [EvalCase.model_validate(item) for item in data]

    def get_evaluation_kb_id(self, db: Session) -> UUID | None:
        settings = get_settings()
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == settings.evaluation_kb_name))
        return kb.id if kb else None

    def ensure_evaluation_kb_ready(
        self,
        db: Session,
        cases_path: Path | None = None,
    ) -> EvaluationReadiness:
        settings = get_settings()
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == settings.evaluation_kb_name))
        if not kb:
            expected_documents = sorted(
                {
                    case.expected_document
                    for case in self.load_eval_cases(cases_path)
                    if case.should_have_answer and case.expected_document
                }
            )
            return EvaluationReadiness(
                evaluation_kb_id=None,
                evaluation_kb_ready=False,
                missing_documents=expected_documents,
                unindexed_documents=[],
            )

        documents = list(db.scalars(select(Document).where(Document.knowledge_base_id == kb.id)).all())
        missing_documents: list[str] = []
        matched_documents: dict[str, Document] = {}
        for case in self.load_eval_cases(cases_path):
            if not case.should_have_answer or not case.expected_document:
                continue
            expected = case.expected_document.lower()
            match = next(
                (
                    document
                    for document in documents
                    if expected in document.filename.lower()
                    or expected in str((document.meta or {}).get("document_title", "")).lower()
                ),
                None,
            )
            if match:
                matched_documents[case.expected_document] = match
            else:
                missing_documents.append(case.expected_document)

        unindexed_documents = sorted(
            {
                str((document.meta or {}).get("document_title") or document.filename)
                for document in matched_documents.values()
                if document.status != DocumentStatus.indexed
            }
        )
        return EvaluationReadiness(
            evaluation_kb_id=kb.id,
            evaluation_kb_ready=not missing_documents and not unindexed_documents,
            missing_documents=sorted(set(missing_documents)),
            unindexed_documents=unindexed_documents,
        )

    async def run_retrieval_eval(
        self,
        db: Session,
        user: User,
        knowledge_base_ids: list[UUID] | None = None,
        cases_path: Path | None = None,
        persist: bool = True,
        use_metadata_filter: bool = False,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
        mode: str = "single",
    ) -> RetrievalEvaluationResponse:
        readiness = self.ensure_evaluation_kb_ready(db, cases_path)
        if not readiness.evaluation_kb_ready or readiness.evaluation_kb_id is None:
            raise RuntimeError(
                "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first."
            )
        kb_ids = knowledge_base_ids or [readiness.evaluation_kb_id]
        cases = self.load_eval_cases(cases_path)
        case_signature = build_evaluation_case_set_signature(cases)
        case_ids = [case.id for case in cases]
        results = [
            await self.evaluate_case(
                db=db,
                user=user,
                case=case,
                knowledge_base_ids=kb_ids,
                use_metadata_filter=use_metadata_filter,
                use_rerank=use_rerank,
                rerank_top_n=rerank_top_n,
            )
            for case in cases
        ]
        metrics = self.calculate_metrics(
            results,
            use_metadata_filter=use_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
            mode=mode,
        )
        failed_cases = [result.model_dump(mode="json") for result in results if not result.passed]
        run_id = None
        if persist:
            run = EvaluationRun(
                eval_type=EvaluationType.retrieval,
                total_cases=len(cases),
                metrics=metrics.model_dump(mode="json"),
                failed_cases=[],
                config_snapshot=build_retrieval_config_snapshot(
                    use_metadata_filter=use_metadata_filter,
                    use_rerank=use_rerank,
                    rerank_top_n=rerank_top_n,
                    mode=mode,
                    evaluation_case_set_signature=case_signature,
                    evaluation_case_ids=case_ids,
                ),
                created_by=user.id,
            )
            db.add(run)
            db.flush()
            results = self._persist_retrieval_case_results(
                db=db,
                run=run,
                cases=cases,
                results=results,
                use_rerank=use_rerank,
            )
            failed_cases = [result.model_dump(mode="json") for result in results if not result.passed]
            run.failed_cases = failed_cases
            db.commit()
            db.refresh(run)
            run_id = run.id
        return RetrievalEvaluationResponse(
            run_id=run_id,
            evaluation_kb_id=readiness.evaluation_kb_id,
            evaluation_kb_ready=readiness.evaluation_kb_ready,
            missing_documents=readiness.missing_documents,
            unindexed_documents=readiness.unindexed_documents,
            total_cases=metrics.total_cases,
            use_metadata_filter=metrics.use_metadata_filter,
            use_rerank=metrics.use_rerank,
            rerank_top_n=metrics.rerank_top_n,
            mode=metrics.mode,
            hit_at_1=metrics.hit_at_1,
            hit_at_3=metrics.hit_at_3,
            hit_at_5=metrics.hit_at_5,
            mrr=metrics.mrr,
            keyword_match_rate=metrics.keyword_match_rate,
            metadata_match_rate=metrics.metadata_match_rate,
            no_answer_accuracy=metrics.no_answer_accuracy,
            failed_cases=failed_cases,
            case_results=results,
        )

    async def evaluate_case(
        self,
        db: Session,
        user: User,
        case: EvalCase,
        knowledge_base_ids: list[UUID],
        top_k: int = 5,
        no_answer_score_threshold: float = 0.2,
        use_metadata_filter: bool = False,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
    ) -> EvalCaseResult:
        used_metadata_filter = self._case_metadata_filter(case) if use_metadata_filter else {}
        retrieval_service = self.retrieval_service or RetrievalService()
        result_set = await retrieval_service.search_with_options(
            db=db,
            user=user,
            query=case.query,
            knowledge_base_ids=knowledge_base_ids,
            top_k=top_k,
            score_threshold=None,
            metadata_filter=used_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
        )
        results = result_set.results
        top_results = [
            {
                "rank": index,
                "filename": result.filename,
                "document_name": result.filename,
                "score": result.score,
                "chunk_id": str(result.chunk_id),
                "document_id": str(result.document_id),
                "chunk_excerpt": result.chunk_text[:1200],
                "chunk_metadata": result.metadata or {},
                "metadata": result.metadata or {},
                "vector_score": result.vector_score,
                "rerank_score": result.rerank_score,
                "final_score": result.final_score,
                "citation": {
                    "filename": result.filename,
                    "page_number": result.page_number,
                    "section_title": result.section_title,
                    "sheet_name": (result.metadata or {}).get("sheet_name"),
                    "row_start": (result.metadata or {}).get("row_start"),
                    "row_end": (result.metadata or {}).get("row_end"),
                    "chunk_id": str(result.chunk_id),
                    "quote": result.chunk_text[:300],
                },
            }
            for index, result in enumerate(results[:top_k], start=1)
        ]
        hit_rank = self._hit_rank(case, results[:top_k])
        keyword_rate = self._keyword_match_rate(case.expected_keywords, results[:top_k])
        metadata_rate = self._metadata_match_rate(case.expected_metadata, results[:top_k])
        no_answer_correct = None
        if not case.should_have_answer:
            max_score = max((result.score for result in results), default=0.0)
            no_answer_correct = len(results) == 0 or max_score < no_answer_score_threshold
        passed = (
            (hit_rank is not None and keyword_rate > 0 and metadata_rate >= 0.5)
            if case.should_have_answer
            else bool(no_answer_correct)
        )
        return EvalCaseResult(
            id=case.id,
            category=case.category,
            query=case.query,
            should_have_answer=case.should_have_answer,
            hit_rank=hit_rank,
            hit_at_1=bool(hit_rank and hit_rank <= 1),
            hit_at_3=bool(hit_rank and hit_rank <= 3),
            hit_at_5=bool(hit_rank and hit_rank <= 5),
            reciprocal_rank=(1.0 / hit_rank) if hit_rank else 0.0,
            keyword_match_rate=keyword_rate,
            metadata_match_rate=metadata_rate,
            no_answer_correct=no_answer_correct,
            passed=passed,
            used_metadata_filter=used_metadata_filter,
            rerank_applied=result_set.rerank_applied,
            rerank_error=result_set.rerank_error,
            top_results=top_results,
        )

    def calculate_metrics(
        self,
        results: list[EvalCaseResult],
        use_metadata_filter: bool = False,
        use_rerank: bool = False,
        rerank_top_n: int | None = None,
        mode: str = "single",
    ) -> EvaluationMetrics:
        total = len(results)
        answerable = [result for result in results if result.should_have_answer]
        no_answer = [result for result in results if not result.should_have_answer]
        denominator = len(answerable) or 1
        no_answer_denominator = len(no_answer) or 1
        return EvaluationMetrics(
            total_cases=total,
            use_metadata_filter=use_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
            mode=mode,
            hit_at_1=sum(1 for result in answerable if result.hit_at_1) / denominator,
            hit_at_3=sum(1 for result in answerable if result.hit_at_3) / denominator,
            hit_at_5=sum(1 for result in answerable if result.hit_at_5) / denominator,
            mrr=sum(result.reciprocal_rank for result in answerable) / denominator,
            keyword_match_rate=sum(result.keyword_match_rate for result in answerable) / denominator,
            metadata_match_rate=sum(result.metadata_match_rate for result in answerable) / denominator,
            no_answer_accuracy=sum(1 for result in no_answer if result.no_answer_correct) / no_answer_denominator,
        )

    @staticmethod
    def _case_metadata_filter(case: EvalCase) -> dict:
        if case.expected_metadata:
            return sanitize_metadata_filter(case.expected_metadata)
        return extract_metadata_from_query(case.query)

    def _persist_retrieval_case_results(
        self,
        db: Session,
        run: EvaluationRun,
        cases: list[EvalCase],
        results: list[EvalCaseResult],
        use_rerank: bool,
    ) -> list[EvalCaseResult]:
        cases_by_id = {case.id: case for case in cases}
        updated_results: list[EvalCaseResult] = []
        for result in results:
            case = cases_by_id[result.id]
            record = EvaluationCaseResultRecord(
                evaluation_run_id=run.id,
                case_id=case.id,
                assistant_type=case.assistant_type or case.category,
                query=case.query,
                expected_document=case.expected_document,
                expected_keywords=case.expected_keywords,
                expected_metadata=case.expected_metadata,
                should_have_answer=case.should_have_answer,
                passed=result.passed,
                failure_reason=None if result.passed else "retrieval_expectation_failed",
                suggested_fix_type=None if result.passed else "metadata_filter",
                used_metadata_filter=result.used_metadata_filter,
                use_rerank=use_rerank,
                rerank_applied=result.rerank_applied,
                answer_excerpt=None,
                citations=[],
                retrieved_results=self._trim_retrieved_results(result.top_results),
            )
            db.add(record)
            db.flush()
            updated_results.append(result.model_copy(update={"case_result_id": record.id}))
        return updated_results

    def _persist_assistant_case_results(
        self,
        db: Session,
        run: EvaluationRun,
        cases: list[EvalCase],
        results: list[AssistantEvaluationCaseResult],
        use_rerank: bool,
    ) -> list[AssistantEvaluationCaseResult]:
        cases_by_id = {case.id: case for case in cases}
        updated_results: list[AssistantEvaluationCaseResult] = []
        for result in results:
            case = cases_by_id[result.id]
            record = EvaluationCaseResultRecord(
                evaluation_run_id=run.id,
                case_id=case.id,
                assistant_type=result.assistant_type,
                query=case.query,
                expected_document=case.expected_document,
                expected_keywords=case.expected_keywords,
                expected_metadata=case.expected_metadata,
                should_have_answer=case.should_have_answer,
                passed=result.passed,
                failure_reason=None if result.passed else result.failure_reason,
                suggested_fix_type=None if result.passed else result.suggested_fix_type,
                used_metadata_filter=result.used_metadata_filter,
                use_rerank=use_rerank,
                rerank_applied=result.rerank_applied,
                answer_excerpt=(result.answer_excerpt or "")[:1200] if result.answer_excerpt else None,
                citations=result.citations,
                retrieved_results=self._trim_retrieved_results(result.retrieved_results),
            )
            db.add(record)
            db.flush()
            updated_results.append(result.model_copy(update={"case_result_id": record.id}))
        return updated_results

    @staticmethod
    def _trim_retrieved_results(results: list[dict]) -> list[dict]:
        trimmed: list[dict] = []
        for index, item in enumerate(results, start=1):
            chunk_excerpt = str(item.get("chunk_excerpt") or item.get("quote") or "")[:1200]
            trimmed.append(
                {
                    "rank": item.get("rank") or index,
                    "document_id": item.get("document_id"),
                    "document_name": item.get("document_name") or item.get("filename"),
                    "chunk_id": item.get("chunk_id"),
                    "chunk_excerpt": chunk_excerpt,
                    "chunk_metadata": item.get("chunk_metadata") or item.get("metadata") or {},
                    "vector_score": item.get("vector_score"),
                    "rerank_score": item.get("rerank_score"),
                    "final_score": item.get("final_score") or item.get("score"),
                    "citation": item.get("citation"),
                }
            )
        return trimmed

    async def compare_retrieval_eval(
        self,
        db: Session,
        user: User,
        rerank_top_n: int | None = None,
    ) -> RetrievalEvaluationCompareResponse:
        baseline = await self.run_retrieval_eval(
            db=db,
            user=user,
            use_metadata_filter=False,
            use_rerank=False,
            persist=True,
            mode="baseline",
        )
        metadata_filter = await self.run_retrieval_eval(
            db=db,
            user=user,
            use_metadata_filter=True,
            use_rerank=False,
            persist=True,
            mode="metadata_filter",
        )
        metadata_filter_rerank = await self.run_retrieval_eval(
            db=db,
            user=user,
            use_metadata_filter=True,
            use_rerank=True,
            rerank_top_n=rerank_top_n,
            persist=True,
            mode="metadata_filter_rerank",
        )
        return RetrievalEvaluationCompareResponse(
            baseline=baseline,
            metadata_filter=metadata_filter,
            metadata_filter_rerank=metadata_filter_rerank,
            delta={
                "metadata_filter_vs_baseline": self._metrics_delta(metadata_filter, baseline),
                "metadata_filter_rerank_vs_baseline": self._metrics_delta(metadata_filter_rerank, baseline),
                "metadata_filter_rerank_vs_metadata_filter": self._metrics_delta(metadata_filter_rerank, metadata_filter),
            },
        )

    @staticmethod
    def _metrics_delta(current: RetrievalEvaluationResponse, previous: RetrievalEvaluationResponse) -> dict[str, float]:
        return {
            "hit_at_1": current.hit_at_1 - previous.hit_at_1,
            "hit_at_3": current.hit_at_3 - previous.hit_at_3,
            "mrr": current.mrr - previous.mrr,
            "metadata_match_rate": current.metadata_match_rate - previous.metadata_match_rate,
            "no_answer_accuracy": current.no_answer_accuracy - previous.no_answer_accuracy,
        }

    @staticmethod
    def _hit_rank(case: EvalCase, results: list[RetrievedChunk]) -> int | None:
        if not case.expected_document:
            return None
        expected = case.expected_document.lower()
        for index, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            document_title = str(metadata.get("document_title") or "")
            if expected in result.filename.lower() or expected in document_title.lower():
                return index
        return None

    @staticmethod
    def _keyword_match_rate(keywords: list[str], results: list[RetrievedChunk]) -> float:
        if not keywords:
            return 1.0
        text = "\n".join(result.chunk_text for result in results).lower()
        hits = sum(1 for keyword in keywords if keyword.lower() in text)
        return hits / len(keywords)

    @staticmethod
    def _metadata_match_rate(expected_metadata: dict[str, str], results: list[RetrievedChunk]) -> float:
        if not expected_metadata:
            return 1.0
        hits = 0
        for key, expected_value in expected_metadata.items():
            expected = str(expected_value).lower()
            if any(expected == str((result.metadata or {}).get(key, "")).lower() for result in results):
                hits += 1
        return hits / len(expected_metadata)

    async def run_assistant_eval(
        self,
        db: Session,
        user: User,
        cases_path: Path | None = None,
        use_metadata_filter: bool = True,
        use_rerank: bool = True,
        rerank_top_n: int | None = None,
        mode: str = "single",
        persist: bool = True,
        run_label: str | None = None,
        change_type: str | None = "unknown",
        change_summary: str | None = None,
        operator_notes: str | None = None,
    ) -> AssistantEvaluationResponse:
        readiness = self.ensure_evaluation_kb_ready(db, cases_path)
        if not readiness.evaluation_kb_ready:
            raise RuntimeError(
                "Evaluation KB is not ready. Run backend/scripts/import_evaluation_fixtures.py first."
            )
        cases = [case for case in self.load_eval_cases(cases_path) if case.assistant_type]
        case_signature = build_evaluation_case_set_signature(cases)
        case_ids = [case.id for case in cases]
        case_results = [
            await self._evaluate_assistant_case(
                db=db,
                user=user,
                case=case,
                use_metadata_filter=use_metadata_filter,
                use_rerank=use_rerank,
                rerank_top_n=rerank_top_n,
            )
            for case in cases
        ]
        per_assistant_metrics = self._assistant_metrics_by_type(case_results)
        assistant_types = sorted(per_assistant_metrics.keys())
        normalized_change_type = validate_change_type(change_type)
        config_snapshot = build_assistant_config_snapshot(
            use_metadata_filter=use_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
            assistant_types=assistant_types,
            mode=mode,
            evaluation_case_set_signature=case_signature,
            evaluation_case_ids=case_ids,
        )
        overall_metrics = self._assistant_metrics("overall", case_results)
        (
            per_assistant_metrics,
            overall_metrics,
            per_assistant_quality_gate,
            quality_gate_passed,
            failed_thresholds,
            threshold_config,
        ) = self._apply_assistant_quality_gates(per_assistant_metrics, overall_metrics)
        failed_cases = [case for case in case_results if not case.passed]
        run_id = None
        created_at = None
        response = AssistantEvaluationResponse(
            run_id=None,
            total_cases=len(case_results),
            use_metadata_filter=use_metadata_filter,
            use_rerank=use_rerank,
            rerank_top_n=rerank_top_n,
            mode=mode,
            run_label=run_label,
            change_type=normalized_change_type,
            change_summary=change_summary,
            operator_notes=operator_notes,
            config_snapshot=config_snapshot,
            overall_metrics=overall_metrics,
            per_assistant_metrics=per_assistant_metrics,
            metrics_by_assistant=per_assistant_metrics,
            failed_cases=failed_cases,
            case_results=case_results,
            quality_gate_passed=quality_gate_passed,
            failed_thresholds=failed_thresholds,
            threshold_config=threshold_config,
            per_assistant_quality_gate=per_assistant_quality_gate,
        )
        if persist:
            run = EvaluationRun(
                eval_type=EvaluationType.assistant,
                total_cases=len(case_results),
                metrics={
                    "use_metadata_filter": use_metadata_filter,
                    "use_rerank": use_rerank,
                    "rerank_top_n": rerank_top_n,
                    "mode": mode,
                    "overall_metrics": overall_metrics.model_dump(mode="json"),
                    "per_assistant_metrics": {
                        key: value.model_dump(mode="json") for key, value in per_assistant_metrics.items()
                    },
                    "quality_gate_passed": quality_gate_passed,
                    "failed_thresholds": failed_thresholds,
                    "threshold_config": threshold_config,
                    "per_assistant_quality_gate": per_assistant_quality_gate,
                },
                failed_cases=[],
                run_label=run_label,
                change_type=normalized_change_type,
                change_summary=change_summary,
                operator_notes=operator_notes,
                config_snapshot=config_snapshot,
                created_by=user.id,
            )
            db.add(run)
            db.flush()
            case_results = self._persist_assistant_case_results(
                db=db,
                run=run,
                cases=cases,
                results=case_results,
                use_rerank=use_rerank,
            )
            failed_cases = [case for case in case_results if not case.passed]
            run.failed_cases = [case.model_dump(mode="json") for case in failed_cases]
            db.commit()
            db.refresh(run)
            run_id = run.id
            created_at = run.created_at
        return response.model_copy(
            update={
                "run_id": run_id,
                "created_at": created_at,
                "failed_cases": failed_cases,
                "case_results": case_results,
            }
        )

    async def _evaluate_assistant_case(
        self,
        db: Session,
        user: User,
        case: EvalCase,
        use_metadata_filter: bool = True,
        use_rerank: bool = True,
        rerank_top_n: int | None = None,
    ) -> AssistantEvaluationCaseResult:
        response = await self.assistant_service.chat(
            db=db,
            user=user,
            assistant_type=case.assistant_type or case.category,
            payload=AssistantChatRequest(
                query=case.query,
                metadata_filter=case.expected_metadata if use_metadata_filter else None,
                auto_metadata_filter=use_metadata_filter,
                use_rerank=use_rerank,
                rerank_top_n=rerank_top_n,
                top_k=5,
                disable_preset_metadata_filter=not use_metadata_filter,
            ),
        )
        actual_top_documents = [citation.filename for citation in response.citations]
        citation_chunks = [
            RetrievedChunk(
                chunk_text=citation.quote,
                filename=citation.filename,
                page_number=citation.page_number,
                score=1.0,
                document_id=UUID(int=0),
                chunk_id=citation.chunk_id,
                section_title=citation.section_title,
                metadata=response.used_metadata_filter,
            )
            for citation in response.citations
        ]
        hit_rank = self._hit_rank(case, citation_chunks)
        keyword_rate = self._keyword_match_rate(case.expected_keywords, citation_chunks)
        metadata_rate = 1.0 if not case.expected_metadata else self._metadata_match_rate(case.expected_metadata, citation_chunks)
        no_answer_correct = None
        if not case.should_have_answer:
            no_answer_correct = response.no_answer_detected
        citation_present = bool(response.citations)
        passed = (
            (hit_rank is not None and keyword_rate > 0 and metadata_rate >= 0.5 and citation_present)
            if case.should_have_answer
            else bool(no_answer_correct)
        )
        reason = None
        if not passed:
            if case.should_have_answer and not citation_present:
                reason = "missing_citation"
            elif case.should_have_answer and hit_rank is None:
                reason = "expected_document_not_cited"
            elif case.should_have_answer and keyword_rate <= 0:
                reason = "expected_keywords_not_found"
            elif case.should_have_answer and metadata_rate < 0.5:
                reason = "expected_metadata_not_matched"
            else:
                reason = "no_answer_expectation_failed"
        result = AssistantEvaluationCaseResult(
            id=case.id,
            assistant_type=case.assistant_type or case.category,
            category=case.category,
            query=case.query,
            passed=passed,
            citation_present=citation_present,
            no_answer_correct=no_answer_correct,
            keyword_match_rate=keyword_rate,
            metadata_match_rate=metadata_rate,
            hit_at_1=bool(hit_rank and hit_rank <= 1),
            hit_at_3=bool(hit_rank and hit_rank <= 3),
            hit_at_5=bool(hit_rank and hit_rank <= 5),
            expected_document=case.expected_document,
            actual_top_documents=actual_top_documents,
            expected_metadata=case.expected_metadata,
            used_metadata_filter=response.used_metadata_filter,
            use_rerank=response.use_rerank,
            rerank_applied=response.rerank_applied,
            answer_excerpt=response.answer[:1200],
            citations=[citation.model_dump(mode="json") for citation in response.citations],
            retrieved_results=response.retrieved_results,
            reason=reason,
        )
        if not result.passed:
            result = result.model_copy(update=analyze_failed_case(case, result))
        return result

    def _assistant_metrics_by_type(
        self,
        case_results: list[AssistantEvaluationCaseResult],
    ) -> dict[str, AssistantEvaluationMetrics]:
        return {
            assistant_type: self._assistant_metrics(
                assistant_type,
                [case for case in case_results if case.assistant_type == assistant_type],
            )
            for assistant_type in sorted({case.assistant_type for case in case_results})
        }

    @staticmethod
    def _assistant_metrics(
        assistant_type: str,
        scoped: list[AssistantEvaluationCaseResult],
    ) -> AssistantEvaluationMetrics:
        answerable = [case for case in scoped if case.no_answer_correct is None]
        no_answer = [case for case in scoped if case.no_answer_correct is not None]
        denominator = len(answerable) or 1
        no_answer_accuracy = (
            sum(1 for case in no_answer if case.no_answer_correct) / len(no_answer)
            if no_answer
            else 1.0
        )
        failed_cases = [case.model_dump(mode="json") for case in scoped if not case.passed]
        return AssistantEvaluationMetrics(
            assistant_type=assistant_type,
            total_cases=len(scoped),
            hit_at_1=sum(1 for case in answerable if case.hit_at_1) / denominator,
            hit_at_3=sum(1 for case in answerable if case.hit_at_3) / denominator,
            hit_at_5=sum(1 for case in answerable if case.hit_at_5) / denominator,
            mrr=sum((1.0 if case.hit_at_1 else 1 / 3 if case.hit_at_3 else 1 / 5 if case.hit_at_5 else 0.0) for case in answerable) / denominator,
            keyword_match_rate=sum(case.keyword_match_rate for case in answerable) / denominator,
            metadata_match_rate=sum(case.metadata_match_rate for case in answerable) / denominator,
            no_answer_accuracy=no_answer_accuracy,
            citation_rate=sum(1 for case in scoped if case.citation_present) / (len(scoped) or 1),
            failed_cases=failed_cases,
        )

    @staticmethod
    def _apply_assistant_quality_gates(
        per_assistant_metrics: dict[str, AssistantEvaluationMetrics],
        overall_metrics: AssistantEvaluationMetrics,
    ) -> tuple[
        dict[str, AssistantEvaluationMetrics],
        AssistantEvaluationMetrics,
        dict[str, dict],
        bool,
        list[dict],
        dict,
    ]:
        per_assistant_quality_gate: dict[str, dict] = {}
        updated_metrics: dict[str, AssistantEvaluationMetrics] = {}
        all_failed_thresholds: list[dict] = []
        threshold_config = get_assistant_quality_thresholds()
        for assistant_type, metrics in per_assistant_metrics.items():
            gate = evaluate_quality_gate(assistant_type, metrics)
            per_assistant_quality_gate[assistant_type] = gate
            failed_thresholds = [
                {"assistant_type": assistant_type, **item} for item in gate["failed_thresholds"]
            ]
            all_failed_thresholds.extend(failed_thresholds)
            updated_metrics[assistant_type] = metrics.model_copy(
                update={
                    "quality_gate_passed": gate["quality_gate_passed"],
                    "failed_thresholds": failed_thresholds,
                    "threshold_config": gate["threshold_config"],
                }
            )
        quality_gate_passed = not all_failed_thresholds
        updated_overall = overall_metrics.model_copy(
            update={
                "quality_gate_passed": quality_gate_passed,
                "failed_thresholds": all_failed_thresholds,
                "threshold_config": threshold_config,
            }
        )
        return (
            updated_metrics,
            updated_overall,
            per_assistant_quality_gate,
            quality_gate_passed,
            all_failed_thresholds,
            threshold_config,
        )

    async def compare_assistant_eval(
        self,
        db: Session,
        user: User,
        cases_path: Path | None = None,
        rerank_top_n: int | None = None,
    ) -> AssistantEvaluationCompareResponse:
        baseline = await self.run_assistant_eval(
            db=db,
            user=user,
            cases_path=cases_path,
            use_metadata_filter=False,
            use_rerank=False,
            rerank_top_n=rerank_top_n,
            mode="baseline",
        )
        metadata_filter = await self.run_assistant_eval(
            db=db,
            user=user,
            cases_path=cases_path,
            use_metadata_filter=True,
            use_rerank=False,
            rerank_top_n=rerank_top_n,
            mode="metadata_filter",
        )
        metadata_filter_rerank = await self.run_assistant_eval(
            db=db,
            user=user,
            cases_path=cases_path,
            use_metadata_filter=True,
            use_rerank=True,
            rerank_top_n=rerank_top_n,
            mode="metadata_filter_rerank",
        )
        return AssistantEvaluationCompareResponse(
            baseline=baseline,
            metadata_filter=metadata_filter,
            metadata_filter_rerank=metadata_filter_rerank,
            delta={
                "metadata_filter_vs_baseline": self._assistant_delta(metadata_filter, baseline),
                "metadata_filter_rerank_vs_baseline": self._assistant_delta(metadata_filter_rerank, baseline),
                "metadata_filter_rerank_vs_metadata_filter": self._assistant_delta(metadata_filter_rerank, metadata_filter),
            },
        )

    @staticmethod
    def _assistant_delta(
        current: AssistantEvaluationResponse,
        previous: AssistantEvaluationResponse,
    ) -> dict[str, float]:
        return {
            "hit_at_1": current.overall_metrics.hit_at_1 - previous.overall_metrics.hit_at_1,
            "mrr": current.overall_metrics.mrr - previous.overall_metrics.mrr,
            "citation_rate": current.overall_metrics.citation_rate - previous.overall_metrics.citation_rate,
            "no_answer_accuracy": current.overall_metrics.no_answer_accuracy - previous.overall_metrics.no_answer_accuracy,
        }

    @staticmethod
    def assistant_response_from_run(run: EvaluationRun) -> AssistantEvaluationResponse:
        metrics = run.metrics or {}
        per_assistant = {
            key: AssistantEvaluationMetrics.model_validate(value)
            for key, value in (metrics.get("per_assistant_metrics") or {}).items()
        }
        overall = AssistantEvaluationMetrics.model_validate(
            metrics.get("overall_metrics")
            or {
                "assistant_type": "overall",
                "total_cases": run.total_cases,
                "hit_at_1": 0,
                "hit_at_3": 0,
                "hit_at_5": 0,
                "mrr": 0,
                "keyword_match_rate": 0,
                "metadata_match_rate": 0,
                "no_answer_accuracy": 0,
                "citation_rate": 0,
            }
        )
        failed_cases = [AssistantEvaluationCaseResult.model_validate(item) for item in (run.failed_cases or [])]
        return AssistantEvaluationResponse(
            run_id=run.id,
            total_cases=run.total_cases,
            use_metadata_filter=bool(metrics.get("use_metadata_filter", True)),
            use_rerank=bool(metrics.get("use_rerank", True)),
            rerank_top_n=metrics.get("rerank_top_n"),
            mode=str(metrics.get("mode", "single")),
            created_at=run.created_at,
            run_label=run.run_label,
            change_type=run.change_type,
            change_summary=run.change_summary,
            operator_notes=run.operator_notes,
            config_snapshot=run.config_snapshot,
            overall_metrics=overall,
            per_assistant_metrics=per_assistant,
            metrics_by_assistant=per_assistant,
            failed_cases=failed_cases,
            case_results=[],
            quality_gate_passed=bool(metrics.get("quality_gate_passed", True)),
            failed_thresholds=metrics.get("failed_thresholds") or [],
            threshold_config=metrics.get("threshold_config") or get_assistant_quality_thresholds(),
            per_assistant_quality_gate=metrics.get("per_assistant_quality_gate") or {},
        )
