# Task 017: Real Retrieval Evaluation Harness

## Goal

Add a real retrieval evaluation harness that can call the existing CoreKB evaluation API against a running deployment when an operator explicitly opts in.

The harness should bridge the earlier read-only fixture baseline and fake-retrieval smoke test to the existing API-backed retrieval evaluation workflow.

## Scope

Allowed paths:

- `Makefile`
- `scripts/`
- `backend/app/tests/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Forbidden paths:

- backend runtime API, service, ingestion, indexing, retrieval, embedding, vector store, database model, or migration code
- frontend runtime code
- production configuration

## Hard Constraints

- Do not modify application runtime behavior.
- Do not modify database schema.
- Do not create migrations.
- Do not add dependencies.
- Do not call LLMs directly from the harness.
- Do not connect directly to PostgreSQL, Qdrant, Redis, Celery, embedding providers, or rerank providers.
- Do not import backend runtime services into the harness.
- Do not mutate documents, metadata, validation reports, suggestions, fixtures, or production data directly.
- Do not weaken or narrow tests to hide failures.

## Acceptance Criteria

- A real retrieval evaluation harness exists under `scripts/`.
- The harness calls existing API endpoints only.
- The harness supports single-run and compare modes.
- The harness requires an admin token.
- The harness requires an explicit persistence confirmation because the API creates evaluation run records.
- The harness returns structured JSON with endpoint, mode, persistence behavior, metrics summary, and API response.
- The harness redacts tokens from output and errors.
- `make eval-real` exists as a convenience target.
- Tests cover endpoint construction, payload construction, persistence guardrails, token redaction, and successful transport handling.
- Documentation explains when to use `make eval`, `make eval-smoke`, and `make eval-real`.
- `agent/results/017_result.md` exists and passes the result checker.

## Verification

Run:

```bash
python -m pytest app/tests/test_real_retrieval_evaluation_harness.py -q
python -m pytest -q
python scripts/check_agent_result.py agent/results/017_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

Optional manual command against a running CoreKB API:

```bash
COREKB_ADMIN_TOKEN=... python scripts/run_real_retrieval_evaluation.py --api-base-url http://localhost:8000 --confirm-persist
```

## Notes

This task intentionally does not add a new backend endpoint. It only adds a CLI harness around the existing retrieval evaluation API.
