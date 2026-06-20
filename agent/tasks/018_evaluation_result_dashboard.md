# Task 018: Evaluation Result Dashboard

## Goal

Add a lightweight evaluation result dashboard for administrators so recent retrieval and assistant evaluation outcomes are visible without opening the full evaluation workbench first.

## Scope

Allowed paths:

- `frontend/src/`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Forbidden paths:

- backend runtime API, service, ingestion, indexing, retrieval, embedding, vector store, database model, or migration code
- production configuration
- evaluation write behavior

## Hard Constraints

- Do not modify backend runtime behavior.
- Do not modify database schema.
- Do not create migrations.
- Do not add dependencies.
- Do not call LLMs.
- Do not create, update, or delete evaluation runs.
- Do not mutate documents, metadata, suggestions, annotations, improvement items, or production data.
- Do not add charts or BI dashboard dependencies.
- Do not weaken or narrow tests to hide failures.

## Acceptance Criteria

- Admin navigation includes an Evaluation Dashboard entry.
- The dashboard displays latest retrieval metrics.
- The dashboard displays latest assistant evaluation quality status.
- The dashboard displays recent evaluation runs.
- The dashboard displays trend warnings and recent regression summary.
- The dashboard displays open improvement and annotation counts.
- The dashboard has loading, error, and empty states.
- The dashboard reuses existing API clients and does not add backend endpoints.
- `agent/results/018_result.md` exists and passes the result checker.

## Verification

Run:

```bash
python -m pytest -q
npm install
npm run build
python scripts/check_agent_result.py agent/results/018_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```

## Notes

This dashboard is intentionally a lightweight table-and-card view. The full Evaluation page remains the place to run evaluations, compare runs, drill down failed cases, and manage improvement loops.
