# Task 031: Single Document Reprocess / Reindex UX

## Goal

Improve the single-document reprocess / reindex experience in the knowledge base document UI while reusing the existing `POST /api/documents/{document_id}/retry-indexing` endpoint.

## Scope

Allowed paths:

- `frontend/src/pages/KnowledgeBaseDetail.tsx`
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

## Requirements

1. Make single-document retry/reindex eligibility clearer in the document list and document detail view.
2. Show a confirmation prompt before submitting a single-document reprocess/reindex job.
3. Show a success message with the submitted index job id.
4. Provide a way to open the submitted index job when `onOpenJob` is available.
5. Disable the action while a document is processing or while a retry request is in flight.
6. Keep existing backend endpoint behavior unchanged.
7. Do not add dependencies.

## Acceptance Criteria

- Frontend build passes.
- Canonical backend tests pass.
- Agent result checks pass.
- No migrations or backend runtime pipeline changes are introduced.

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
python scripts/check_agent_result.py agent/results/031_result.md
python scripts/check_agent_result.py "agent/results/*_result.md"
python agent/runner.py check
```
