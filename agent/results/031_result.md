# Task 031 Result

## Summary

Improved the single-document reprocess / reindex UX in the knowledge base document UI using the existing retry-indexing endpoint.

## Files Changed

- `agent/tasks/031_single_document_reprocess_reindex_ux.md`
- `agent/results/031_result.md`
- `docs/INDEXING.md`
- `frontend/src/pages/KnowledgeBaseDetail.tsx`
- `frontend/src/styles.css`

## Behavior Added

- Added clearer retry eligibility handling for single documents.
- Added a confirmation prompt before submitting a single-document reprocess / reindex job.
- Added a document detail reprocess panel with status guidance.
- Added success messaging with the submitted index job id.
- Added a direct "View job" action when index-job navigation is available.
- Disabled reprocess action while submission is in flight.
- Document list now explains why non-eligible documents cannot be retried.

## Tests Run

- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/031_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Frontend build passed.
- Backend tests passed: 340 passed, 1 skipped, 14 warnings.
- Agent result checks passed.
- Agent runner check passed.

## Runtime Impact

Frontend-only UX change. It reuses the existing `POST /api/documents/{document_id}/retry-indexing` API and does not change backend runtime behavior, indexing workers, ingestion, retrieval, embedding, or metadata suggestion logic.

## Database Impact

None. No models, migrations, or persisted data write paths were changed.

## Risk Notes

- The UI follows existing backend eligibility: only `failed`, `uploaded`, and `parsed` documents can be retried.
- Indexed documents remain excluded from this single-document retry endpoint; knowledge-base reindex is the existing rebuild path.
- The confirmation prompt is browser-native and intentionally lightweight.

## Rollback Notes

Revert the KnowledgeBaseDetail, stylesheet, indexing documentation, task file, and result file changes to restore the previous minimal retry button UX.

## Open Questions

- Should a later backend task add an explicit single-document force reindex endpoint for already indexed documents?
