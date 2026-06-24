# Task 032: Force Reprocess Indexed Document

## Goal

Allow editors/admins to explicitly force reprocess an already indexed single document through the existing retry-indexing flow.

## Scope

Allowed paths:

- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/tests/`
- `frontend/src/api/client.ts`
- `frontend/src/pages/KnowledgeBaseDetail.tsx`
- `docs/`
- `agent/tasks/`
- `agent/results/`

Do not modify:

- database models
- migrations
- ingestion/indexing/retrieval/embedding pipeline logic
- production config
- metadata suggestion review behavior

## Requirements

1. Extend `POST /api/documents/{document_id}/retry-indexing` with an optional request body:

```json
{"force": true}
```

2. Keep existing behavior unchanged when `force` is absent or false.
3. Allow `indexed` documents to be retried only when `force=true`.
4. Continue allowing `failed`, `uploaded`, and `parsed` documents without force.
5. Continue rejecting processing states such as `parsing`, `chunking`, and `embedding`.
6. Update frontend single-document reprocess UX to expose a force action for indexed documents.
7. Add tests for indexed-without-force rejection and indexed-with-force success.
8. Do not add migrations or dependencies.

## Acceptance Criteria

- Targeted document task tests pass.
- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No database schema or pipeline logic changes are introduced.

## Verification

Run from `backend/`:

```bash
python -m pytest app/tests/test_document_tasks.py -q
python -m pytest -q
```

Run from `frontend/`:

```bash
npm install
npm run build
```

Run from repo root:

```bash
python scripts/check_agent_result.py agent/results/032_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
