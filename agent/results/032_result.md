# Task 032 Result

## Summary

Added explicit force reprocess support for already indexed documents through the existing single-document retry-indexing endpoint and surfaced it in the document UI.

## Files Changed

- `agent/tasks/032_force_reprocess_indexed_document.md`
- `agent/results/032_result.md`
- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/tests/test_document_tasks.py`
- `docs/INDEXING.md`
- `frontend/src/api/client.ts`
- `frontend/src/pages/KnowledgeBaseDetail.tsx`

## Behavior Added

- `POST /api/documents/{document_id}/retry-indexing` now accepts optional body `{"force": true}`.
- Existing retry behavior remains unchanged when `force` is absent or false.
- `indexed` documents can be submitted for single-document reprocess only with `force=true`.
- Processing states remain rejected.
- Audit metadata records `force` and the previous document status.
- Frontend shows a `Force reprocess` action for indexed documents with stronger confirmation copy.
- Documentation now explains force retry semantics and limits.

## Tests Run

- `python -m pytest app/tests/test_document_tasks.py -q`
- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/032_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Targeted document tests passed: 8 passed.
- Frontend build passed.
- Backend tests passed: 342 passed, 1 skipped, 15 warnings.
- Agent result checks passed.
- Agent runner check passed.

## Runtime Impact

The existing retry-indexing API now supports an explicit force option for indexed documents. It still enqueues the normal document indexing job and does not change worker, ingestion, embedding, retrieval, vector store, or metadata suggestion logic.

## Database Impact

None. No database models or migrations were changed.

## Risk Notes

- Force reprocess resets an indexed document to `uploaded`; chunks and vectors are replaced by the normal worker pipeline.
- Processing states are still rejected to avoid racing active indexing work.
- Existing clients without a request body keep the old behavior.

## Rollback Notes

Revert the API request schema, route force handling, tests, frontend client/UX changes, documentation, task file, and result file to restore the previous retry behavior.

## Open Questions

- Should force reprocess eventually expose a reason/comment field for stronger audit traceability?
