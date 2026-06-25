# Task 034: Maintenance Evidence Panel

## Goal

Improve the Maintenance Knowledge MVP with a dedicated evidence panel so maintenance users can inspect retrieved sources, scores, metadata, and citations without leaving the assistant page.

## Scope

Allowed paths:

- `frontend/src/pages/MaintenanceKnowledgePage.tsx`
- `frontend/src/styles.css`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- backend runtime APIs
- database models
- migrations
- ingestion/indexing/retrieval/embedding logic
- production config
- metadata suggestion review behavior
- assistant prompt or evaluation logic

## Requirements

1. Add a maintenance evidence panel below assistant answers.
2. Reuse `retrieved_results`, `citations`, metadata filter, and rerank fields already returned by the existing assistant chat API.
3. Let users inspect evidence by rank, source document, citation status, scores, metadata, and chunk excerpt.
4. Provide a lightweight cited-only filter and selected evidence detail view.
5. Clearly show whether retrieved evidence is cited in the answer.
6. Keep UI simple and table/card based; do not add charts, workflows, or new backend endpoints.
7. Add documentation for evidence panel behavior and boundaries.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No backend runtime, database, migration, or indexing changes are introduced.

## Verification

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from `backend/`:

```bash
python -m pytest -q
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/034_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
