# Task 015: Evaluation Runner Baseline

## Goal

Replace the placeholder `make eval` command with a small, deterministic, read-only evaluation fixture baseline runner.

The runner should validate the shape of `eval_cases.json` and summarize fixture coverage before any live retrieval, assistant, database, Qdrant, or LLM evaluation is attempted.

## Scope

Allowed paths:

- `Makefile`
- `scripts/`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Forbidden paths:

- backend runtime API, service, ingestion, indexing, retrieval, embedding, or database model code
- frontend runtime code
- migrations
- production configuration

## Hard Constraints

- Do not modify runtime behavior.
- Do not modify database schema.
- Do not create migrations.
- Do not add dependencies.
- Do not call LLMs.
- Do not connect to PostgreSQL, Qdrant, Redis, or Celery.
- Do not mutate fixtures, documents, metadata, validation reports, suggestions, or production data.
- Do not weaken or narrow tests to hide failures.

## Acceptance Criteria

- `make eval` runs a real read-only baseline command instead of a placeholder echo.
- The baseline runner validates evaluation case required fields.
- The baseline runner detects duplicate case ids.
- The baseline runner reports coverage by category, assistant type, answerability, and expected metadata fields.
- The baseline runner exits non-zero for invalid fixture shape.
- Tests cover the runner behavior.
- Documentation explains that this baseline is fixture readiness validation, not live retrieval quality measurement.
- `agent/results/015_result.md` exists and passes the result checker.

## Verification

Run:

```bash
python -m pytest app/tests/test_evaluation_runner_baseline.py -q
python -m pytest -q
python scripts/run_evaluation_baseline.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json
make eval
python scripts/check_agent_result.py agent/results/015_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

## Notes

This task intentionally does not execute live retrieval, assistant chat, rerank, metadata filtering, or any database-backed evaluation run. Those can be wired in a later scoped task once the command contract is stable.
