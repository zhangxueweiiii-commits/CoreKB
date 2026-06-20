## Summary

Implemented Task 021 batch triage operations for evaluation failure triage notes. Admins can now update triage status and notes for multiple evaluation case results in one advisory operation.

## Files Changed

- agent/tasks/021_batch_triage_operations.md
- agent/results/021_result.md
- backend/app/api/routes/evaluation.py
- backend/app/schemas/evaluation.py
- backend/app/services/evaluation_failure_triage_note_service.py
- backend/app/tests/test_evaluation_failure_triage_notes.py
- frontend/src/api/evaluation.ts
- frontend/src/pages/EvaluationFailureTriagePage.tsx
- frontend/src/styles.css
- docs/EVALUATION.md

## Behavior Added

- Added `POST /api/evaluation/triage-notes/batch` for admin-only batch triage note updates.
- Added batch note modes: `replace`, `append`, and `keep`.
- Added frontend selection controls and batch triage toolbar on the Evaluation Failure Triage page.
- Added tests for batch update, deduplication, append mode, keep mode, invalid mode, and missing case result handling.
- Documented that batch triage operations update only advisory triage notes.

## Tests Run

- `python -m pytest app/tests/test_evaluation_failure_triage_notes.py -q`
- `npm install`
- `npm run build`
- `python -m pytest -q`
- `python scripts/check_agent_result.py agent/results/021_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Targeted backend tests: 13 passed.
- Frontend build: passed.
- Canonical backend tests: 320 passed, 1 skipped, 16 warnings.
- Agent result checks: passed for `agent/results/021_result.md`, all result files, and `python agent/runner.py check`.

## Runtime Impact

Adds one read/write admin-only evaluation triage endpoint and a frontend batch action that writes only `evaluation_failure_triage_notes`. It does not change ingestion, embedding, indexing, retrieval, evaluation execution, metadata mutation, prompt, chunking, rerank, or production data pipelines.

## Database Impact

No database schema changes and no migration. Existing `evaluation_failure_triage_notes` rows are reused.

## Risk Notes

Batch actions can update several advisory triage notes at once, so an admin could apply the wrong note/status to selected cases. The UI shows selected count and note mode, and the backend validates case result ids and status values before writing.

## Rollback Notes

Revert this task's changes to remove the batch endpoint and frontend batch controls. Existing single-case triage note behavior remains independent.

## Open Questions

None.
