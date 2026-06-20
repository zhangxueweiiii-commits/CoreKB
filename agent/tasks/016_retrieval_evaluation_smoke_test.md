# Task 016: Retrieval Evaluation Smoke Test

## Goal

Add a deterministic retrieval evaluation smoke test command that exercises the existing `EvaluationService.evaluate_case()` and metric calculation path without live infrastructure.

The smoke test should prove that the evaluation fixtures can be evaluated through a fake retrieval service and produce passing retrieval metrics for the built-in cases.

## Scope

Allowed paths:

- `Makefile`
- `scripts/`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Forbidden paths:

- backend runtime API, ingestion, indexing, retrieval, embedding, vector store, database model, or migration code
- frontend runtime code
- production configuration

## Hard Constraints

- Do not modify application runtime behavior.
- Do not modify database schema.
- Do not create migrations.
- Do not add dependencies.
- Do not call LLMs.
- Do not connect to PostgreSQL, Qdrant, Redis, Celery, embedding providers, rerank providers, or chat models.
- Do not create evaluation runs or case result records.
- Do not mutate documents, metadata, validation reports, suggestions, fixtures, or production data.
- Do not weaken or narrow tests to hide failures.

## Acceptance Criteria

- A retrieval evaluation smoke runner exists under `scripts/`.
- The smoke runner loads `eval_cases.json` and evaluates all cases using deterministic fake retrieval.
- The smoke runner returns structured JSON including metrics, failed cases, runtime dependency flags, and read-only flags.
- The smoke runner exits non-zero if any smoke case fails.
- A `make eval-smoke` target runs the smoke runner.
- Tests cover passing metrics, no-answer behavior, metadata filter usage, and CLI exit behavior.
- Documentation explains that this is not a live retrieval quality test.
- `agent/results/016_result.md` exists and passes the result checker.

## Verification

Run:

```bash
python -m pytest app/tests/test_retrieval_evaluation_smoke.py -q
python -m pytest -q
python scripts/run_retrieval_evaluation_smoke.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json
make eval-smoke
python scripts/check_agent_result.py agent/results/016_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

## Notes

This task intentionally stays below the API/database persistence layer. It exercises retrieval evaluation logic with fake retrieval only. Live Evaluation KB readiness, fixture import, Qdrant search, rerank, and assistant evaluation remain separate workflows.
