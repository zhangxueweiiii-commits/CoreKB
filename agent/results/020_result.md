# Task 020 Result

## Summary

Added persisted failure triage notes for evaluation case results. Admins can now keep lightweight triage status and reviewer notes from the Evaluation Failure Triage page without creating formal annotations or improvement items.

## Files Changed

- `agent/tasks/020_persisted_failure_triage_notes.md`
- `agent/results/020_result.md`
- `backend/app/models/evaluation_triage_note.py`
- `backend/app/db/base.py`
- `backend/alembic/versions/0020_evaluation_failure_triage_notes.py`
- `backend/app/services/evaluation_failure_triage_note_service.py`
- `backend/app/services/evaluation_case_drilldown_service.py`
- `backend/app/schemas/evaluation.py`
- `backend/app/api/routes/evaluation.py`
- `backend/app/tests/conftest.py`
- `backend/app/tests/test_evaluation_failure_triage_notes.py`
- `frontend/src/api/evaluation.ts`
- `frontend/src/pages/EvaluationFailureTriagePage.tsx`
- `frontend/src/styles.css`
- `docs/EVALUATION.md`

## Behavior Added

- Added `evaluation_failure_triage_notes` as one current lightweight note per `evaluation_case_result`.
- Added admin-only APIs to list notes, get a case note, and upsert a case note.
- Added triage status values: `open`, `reviewing`, `resolved`, and `ignored`.
- Included the current triage note in case drill-down payloads.
- Added note editing controls to the Evaluation Failure Triage page.
- Documented that triage notes are advisory and do not mutate production metadata, annotations, improvement items, prompts, chunking, rerank settings, indexes, or source documents.

## Tests Run

- `python -m pytest app/tests/test_evaluation_failure_triage_notes.py app/tests/test_evaluation_case_drilldown.py -q` from `backend/`
- `npm install` from `frontend/`
- `npm run build` from `frontend/`
- `python -m pytest -q` from `backend/`
- `python scripts/check_agent_result.py agent/results/020_result.md`
- `python scripts/check_agent_result.py "agent/results/*_result.md"`
- `python agent/runner.py check`

## Test Result

- Targeted backend tests passed: 12 passed.
- Frontend build passed.
- Backend canonical tests passed: 314 passed, 1 skipped, 16 warnings.
- Agent result checker passed for `agent/results/020_result.md` and all existing result files.
- Agent runner check passed.

## Runtime Impact

Adds admin-only evaluation triage note APIs and a frontend note editor on the existing Failure Triage page. This affects advisory evaluation review behavior only.

## Database Impact

Adds migration `0020_evaluation_failure_triage_notes.py`, creating `evaluation_failure_triage_notes` with a foreign key to `evaluation_case_results` and a unique constraint for one current note per case result.

## Risk Notes

- Triage notes are intentionally lighter than structured case annotations and do not feed improvement item generation.
- Existing historical failed cases without `case_result_id` cannot save triage notes from the page.
- Notes are advisory review records and should not be treated as business truth without structured annotation or follow-up verification.

## Rollback Notes

Revert the migration, model, service, route/schema changes, tests, frontend API/page edits, docs, task file, and result file. If already migrated in an environment, downgrade migration `0020_evaluation_failure_triage_notes` to remove the notes table and enum.

## Open Questions

- Should a future task add a dedicated triage notes list page, or should notes remain embedded only in the Failure Triage page and case drill-down?
